from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import subprocess  # For running the ollama CLI

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

# Function to query the locally running llama2 model using ollama CLI
def query_ollama(user_query: str):
    try:
        # Prepare the prompt for the llama2 model
        prompt = (
            "Extract the following details from the user query:\n"
            "1. Colors (comma-separated list)\n"
            "2. Item types (comma-separated list)\n"
            "If multiple item types are mentioned, include all of them.\n"
            "If no specific item type is mentioned, return 'all'.\n"
            f"User query: {user_query}"
        )

        # Run the ollama CLI command to interact with the llama2 model
        result = subprocess.run(
            ["ollama", "run", "llama2", prompt],
            capture_output=True,
            text=True,
            encoding="utf-8",  # Explicitly set encoding to utf-8
            errors="replace"   # Replace invalid characters instead of raising an error
        )

        # Check for errors
        if result.returncode != 0:
            raise Exception(f"Ollama CLI Error: {result.stderr}")

        # Parse the response to extract details
        response_text = result.stdout.strip()
        print(f"Ollama CLI Response: {response_text}")  # Log the response

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
        print(f"Ollama CLI Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing query with Ollama: {str(e)}")

# FastAPI endpoint to search for products
@app.post("/search")
async def search_product(search_request: SearchRequest):
    query = search_request.query  # Extract the query from the request body

    # Extract details from the query using Ollama
    try:
        ollama_response = query_ollama(query)
        colors = ollama_response.get("colors", ["red"])  # Default to 'red' if no colors are detected
        item_types = ollama_response.get("item_types", ["all"])  # Default to 'all' if not detected
        print("item type : ", item_types)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query with Ollama: {str(e)}")

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