from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from openai import OpenAI
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Initialize FastAPI
app = FastAPI()

# MongoDB Atlas connection details
MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")

# OpenAI API details
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# MongoDB client
client = MongoClient(MONGO_URI)
db = client[DATABASE_NAME]
collection = db[COLLECTION_NAME]

# OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)

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

# Function to query MongoDB
def query_database(colors: list, item_type: str):
    query = {
        "color": {"$in": colors},  # Match any of the specified colors
        "name": {"$regex": item_type, "$options": "i"},  # Case-insensitive search
        "availability": True
    }
    products = collection.find(query)
    return [
        Product(
            id=str(product["_id"]),
            name=product["name"],
            color=product["color"],
            availability=product["availability"],
            image_url=product.get("image_url", "")  # Handle missing image_url
        )
        for product in products
    ]

# Function to query OpenAI API
def query_openai(user_query: str):
    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Extract the colors and item type from the user query. Return the colors as a comma-separated list and the item type as a single word. If no item type is mentioned, return 'all'."},
                {"role": "user", "content": user_query},
            ],
            max_tokens=1024,
            temperature=0.7,
            stream=False
        )
        # Parse the response to extract colors and item type
        response_text = response.choices[0].message.content
        print(f"OpenAI API Response: {response_text}")  # Log the response

        # Initialize default values
        colors = []
        item_type = "all"

        # Extract colors and item type from the response
        if "colors:" in response_text.lower():
            colors_part = response_text.lower().split("colors:")[1].strip()
            colors = [color.strip() for color in colors_part.split(",")]
        if "item type:" in response_text.lower():
            item_type = response_text.lower().split("item type:")[1].strip()

        return {"colors": colors, "item_type": item_type}
    except Exception as e:
        print(f"OpenAI API Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing query with OpenAI: {str(e)}")

# FastAPI endpoint to search for products
@app.post("/search/")
async def search_product(search_request: SearchRequest):
    query = search_request.query  # Extract the query from the request body

    # Extract colors and item type from the query using OpenAI
    try:
        openai_response = query_openai(query)
        colors = openai_response.get("colors", ["red"])  # Default to 'red' if no colors are detected
        item_type = openai_response.get("item_type", "all")  # Default to 'all' if not detected
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query with OpenAI: {str(e)}")

    # Query the database
    if item_type == "all":
        # Search for all item types if no specific type is mentioned
        query = {
            "color": {"$in": colors},
            "availability": True
        }
    else:
        # Search for a specific item type
        query = {
            "color": {"$in": colors},
            "name": {"$regex": item_type, "$options": "i"},
            "availability": True
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