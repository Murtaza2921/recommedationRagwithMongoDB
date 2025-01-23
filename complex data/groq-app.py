from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import re
import json
from dotenv import load_dotenv
import os
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from pymongo import MongoClient
from langchain_groq import ChatGroq

load_dotenv()
app = FastAPI()
MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")

# MongoDB client
client = MongoClient(MONGO_URI)
db = client[DATABASE_NAME]
collection = db[COLLECTION_NAME]


groq_chat = ChatGroq(temperature=0, model_name="mixtral-8x7b-32768")

# Define the request model
class SearchRequest(BaseModel):
    query: str

# Define the product model
class Product(BaseModel):
    id: str
    title: str
    brand: str
    category: str
    sub_category: str
    description: str
    color: str
    selling_price: str
    actual_price: str
    discount: str
    images: list
    out_of_stock: bool
    average_rating: str
    product_details: list

# Function to format the price in the filter_query
def format_price_in_filter(filter_query):
    if isinstance(filter_query, dict):
        for key, value in filter_query.items():
            if key == "actual_price":
                # Handle cases where actual_price is a comparison operator (e.g., {'$lt': '2000'})
                if isinstance(value, dict):
                    for op, op_value in value.items():
                        if isinstance(op_value, str) and op_value.isdigit():
                            value[op] = "{:,}".format(int(op_value))  # Format with commas
                        elif isinstance(op_value, int):
                            value[op] = "{:,}".format(op_value)  # Format with commas
                # Handle cases where actual_price is a direct value (e.g., "2000" or 2000)
                elif isinstance(value, str) and value.isdigit():
                    filter_query[key] = "{:,}".format(int(value))  # Format with commas
                elif isinstance(value, int):
                    filter_query[key] = "{:,}".format(value)  # Format with commas
            elif isinstance(value, dict):
                format_price_in_filter(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        format_price_in_filter(item)
    return filter_query

@app.post("/search")
async def search_product(search_request: SearchRequest):
    query = search_request.query  # Extract the query from the request body

    # Extract the MongoDB query from the user query using Groq
    try:
        filter_query, projection = query_groq(query)
        filter_query = format_price_in_filter(filter_query)  # Format the filter_query
        print("Generated MongoDB filter:", filter_query)  # Log the generated filter
        print("Generated MongoDB projection:", projection)  # Log the generated projection
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query with Groq: {str(e)}")

    # Query the database using the generated filter and projection
    try:
        # Apply filter and projection
        products = collection.find(filter_query, projection)

        # Convert the cursor to a list of products
        product_list = [
            Product(
                id=str(product.get("_id", "")),
                title=product.get("title", "N/A"),
                brand=product.get("brand", "N/A"),
                category=product.get("category", "N/A"),
                sub_category=product.get("sub_category", "N/A"),
                description=product.get("description", "N/A"),
                color=next((detail.get("Color", "N/A") for detail in product.get("product_details", []) if "Color" in detail), "N/A"),
                selling_price=product.get("selling_price", "N/A"),
                actual_price=product.get("actual_price", "N/A"),
                discount=product.get("discount", "N/A"),
                images=product.get("images", []),  # Default to an empty list if 'images' is missing
                out_of_stock=product.get("out_of_stock", False),  # Default to False if 'out_of_stock' is missing
                average_rating=product.get("average_rating", "N/A"),
                product_details=product.get("product_details", [])  # Default to an empty list if 'product_details' is missing
            )
            for product in products
        ]

        if not product_list:
            raise HTTPException(status_code=404, detail="No products found")

        # Limit to the top 5 results if the list has more than 5 items
        top_products = product_list[:5]

        # Format the response in a human-like way
        response_message = f"I found the following products:\n\n"
        for product in top_products:
            response_message += (
                f"- **{product.title}** (Brand: {product.brand}, Category: {product.category}, "
                f"Sub-Category: {product.sub_category}, Color: {product.color}, "
                f"Price: {product.selling_price}, Discount: {product.discount}, "
                f"Availability: {'Available' if not product.out_of_stock else 'Out of stock'})\n"
            )

        return {"message": response_message, "products": top_products}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying the database: {str(e)}")

def query_groq(user_query: str):
    try:
        # Prepare the prompt for the OpenAI model
        prompt = PromptTemplate(
            input_variables=["user_query"],
            template=(
                "You are tasked with generating a MongoDB query based on a user query.\n"
                "The query should be based on a product schema with the following fields:\n"
                "  - _id (UUID)\n"
                "  - actual_price (String, formatted with commas, e.g., '2,999')\n"
                "  - average_rating (String)\n"
                "  - brand (String)\n"
                "  - category (String)\n"
                "  - crawled_at (String)\n"
                "  - description (String)\n"
                "  - discount (String)\n"
                "  - images (Array of Strings, optional)\n"
                "  - out_of_stock (Boolean, optional)\n"
                "  - pid (String)\n"
                "  - product_details (Array of objects with specific keys, optional)\n"
                "  - seller (String)\n"
                "  - selling_price (String)\n"
                "  - sub_category (String)\n"
                "  - title (String)\n"
                "  - url (String)\n"
                
                "Generate a MongoDB query that:\n"
                "- Applies filters on the fields based on the user query.\n"
                "- Specifies the fields to return in the result (projection).\n"
                "- The projection must only include field inclusion/exclusion (e.g., 1 or 0).\n"
                "- Do not include aggregation expressions (e.g., $substr, $cond) in the projection.\n"
                "- Sorts the results if specified by the user.\n"
                "- Limits the number of results if specified by the user.\n"
                "- The `actual_price` field must be treated as a string in both the filter and projection.\n"
                "- The `out_of_stock` field must be a boolean (true or false).\n"
                "Format the response as a valid JSON object with two keys: 'filter' and 'projection'.\n"
                "Do not include explanations or additional text.\n"
                "Here is the user query: {user_query}"
            )
        )

        # Create a RunnableSequence with the prompt and LLM
        chain = (
            {"user_query": RunnablePassthrough()}  # Pass the user query directly
            | prompt  # Apply the prompt template
            | groq_chat  # Use the LLM to generate the response
        )

        # Run the chain with the user query
        response = chain.invoke(user_query)
        print(f"OpenAI Response: {response}")  # Log the response

        # Extract the content from the AIMessage object
        response_text = response.content

        # Use regex to extract the JSON object from the response
        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if not json_match:
            raise ValueError("No JSON object found in the response.")

        json_str = json_match.group(0)

        # Parse the MongoDB query from the response
        try:
            query_dict = json.loads(json_str)
            filter_query = query_dict.get("filter", {})
            projection = query_dict.get("projection", {})
            return filter_query, projection
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse MongoDB query from response: {json_str}")
    except Exception as e:
        print(f"OpenAI Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing query with OpenAI: {str(e)}")
    

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)