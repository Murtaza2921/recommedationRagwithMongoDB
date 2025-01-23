from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
from pydantic import BaseModel
from typing import List
import json
import os

# Initialize FastAPI app
app = FastAPI()

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Get MongoDB connection URI and database name from environment variables
MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")

# Initialize MongoDB client and collection
client = MongoClient(MONGO_URI)
db = client[DATABASE_NAME]
collection = db["flipKart_products"]

# Pydantic model for the ProductDetails
class ProductDetail(BaseModel):
    Style_Code: str
    Closure: str
    Pockets: str
    Fabric: str
    Pattern: str
    Color: str

# Pydantic model for the Product
class Product(BaseModel):
    _id: str
    actual_price: str
    average_rating: str
    brand: str
    category: str
    crawled_at: str
    description: str
    discount: str
    images: List[str]
    out_of_stock: bool
    pid: str
    product_details: List[ProductDetail]
    seller: str
    selling_price: str
    sub_category: str
    title: str
    url: str

# Pydantic model for the request body containing the file path
class FilePathRequest(BaseModel):
    file_path: str

# Function to load data from JSON file
def load_data_from_json(file_path: str):
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    with open(file_path, 'r') as file:
        try:
            data = json.load(file)
            if not isinstance(data, list):
                raise HTTPException(status_code=400, detail="JSON data should be a list of products")
            return data
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail="Invalid JSON format")

# FastAPI Endpoint to insert data from JSON file into MongoDB
@app.post("/insert_products/")
async def insert_products(request: FilePathRequest):
    try:
        # Load the JSON data from the provided file path
        data = load_data_from_json(request.file_path)
        
        if not data:
            raise HTTPException(status_code=400, detail="No data found in the JSON file")
        
        # Insert the data into MongoDB
        result = collection.insert_many(data)
        
        return {"message": "Data inserted successfully", "count": len(result.inserted_ids)}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Run the server with the command:
# uvicorn filename:app --reload

# Run the application (use this only if running as a standalone script)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
