from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq

# Load environment variables
load_dotenv()

# Initialize FastAPI
app = FastAPI()

# MongoDB Atlas connection details
MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")

# MongoDB client
client = MongoClient(MONGO_URI)
db = client[DATABASE_NAME]
collection = db[COLLECTION_NAME]

# Pydantic model for product response
class Product(BaseModel):
    id: str
    name: str
    color: str
    availability: bool
    image_url: str

# Pydantic model for search request
class SearchRequest(BaseModel):
    query: str

# Initialize Groq chat model
groq_chat = ChatGroq(temperature=0, model_name="mixtral-8x7b-32768")

# Function to query the Groq model
def query_groq(user_query: str):
    try:
        # Prepare the prompt for the Groq model
        prompt = PromptTemplate(
            input_variables=["user_query"],
            template=(
                "Extract the following details from the user query:\n"
                "1. Colors (comma-separated list)\n"
                "2. Item types (comma-separated list)\n"
                "If multiple item types are mentioned, include all of them.\n"
                "If no specific item type is mentioned, return 'all'.\n"
                "User query: {user_query}"
            )
        )

        # Create an LLMChain with the Groq model
        chain = LLMChain(llm=groq_chat, prompt=prompt)

        # Run the chain with the user query
        response_text = chain.run(user_query=user_query)
        print(f"Groq Response: {response_text}")  # Log the response

        # Initialize default values
        colors = []
        item_types = []

        # Extract colors and item types from the response
        for line in response_text.split("\n"):
            line = line.strip().lower()
            if "colors:" in line:
                colors_part = line.split("colors:")[1].strip()
                colors = [color.strip() for color in colors_part.split(",")]
            if "item types:" in line:
                item_types_part = line.split("item types:")[1].strip()
                item_types = [item.strip() for item in item_types_part.split(",")]

        return {"colors": colors, "item_types": item_types}
    except Exception as e:
        print(f"Groq Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing query with Groq: {str(e)}")

# FastAPI endpoint to search for products
@app.post("/search")
async def search_product(search_request: SearchRequest):
    query = search_request.query  # Extract the query from the request body

    # Extract details from the query using Groq
    try:
        groq_response = query_groq(query)
        colors = groq_response.get("colors", ["red"])  # Default to 'red' if no colors are detected
        item_types = groq_response.get("item_types", ["all"])  # Default to 'all' if not detected
        print("item type : ", item_types)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query with Groq: {str(e)}")

    # Query the database
    if "all" in item_types:
        # Search for all item types if no specific type is mentioned
        query = {
            "color": {"$in": colors}
        }
    else:
        # Search for specific item types using $or with multiple regex conditions
        query = {
            "color": {"$in": colors},
            "$or": [{"name": {"$regex": item_type, "$options": "i"}} for item_type in item_types]
        }

    products = collection.find(query)
    product_list = [
        Product(
            id=str(product["_id"]),
            name=product["name"],
            color=product["color"],
            availability=product["availability"],
            image_url=product.get("image_url", "")  # Handle missing image_url
        )
        for product in products
    ]

    if not product_list:
        raise HTTPException(status_code=404, detail="No products found")

    # Format the response in a human-like way
    response_message = f"I found the following products in {', '.join(colors)}:\n\n"
    for product in product_list:
        response_message += f"- **{product.name}** (Color: {product.color}, Availability: {'Available' if product.availability else 'Out of stock'})\n"

    return {"message": response_message, "products": product_list}

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)