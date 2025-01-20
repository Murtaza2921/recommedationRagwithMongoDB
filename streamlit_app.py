import streamlit as st
import requests

# FastAPI backend URL
FASTAPI_URL = "http://127.0.0.1:8000"  # Update this to your FastAPI server URL

# Custom CSS for sticky title, sticky input, and scrollable chat history
st.markdown(
    """
    <style>
    /* Sticky title */
    .sticky-title {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        background-color: white;
        padding: 10px;
        border-bottom: 1px solid #ddd;
        z-index: 1000;
    }
    /* Sticky input container */
    .sticky-input {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background-color: white;
        padding: 10px;
        border-top: 1px solid #ddd;
        z-index: 1000;
    }
    /* Scrollable chat history */
    .chat-history {
        height: calc(100vh - 200px);  /* Adjust height based on screen size */
        overflow-y: auto;
        padding: 10px;
        margin-top: 80px;  /* Space for the sticky title */
        margin-bottom: 80px;  /* Space for the sticky input */
    }
    /* Chat bubbles */
    .user-message {
        background-color: #0078D4;
        color: white;
        padding: 10px 15px;
        border-radius: 15px 15px 0 15px;
        margin: 10px 0;
        max-width: 70%;
        margin-left: auto;
        font-size: 14px;
    }
    .bot-message {
        background-color: #F1F1F1;
        color: black;
        padding: 10px 15px;
        border-radius: 15px 15px 15px 0;
        margin: 10px 0;
        max-width: 70%;
        margin-right: auto;
        font-size: 14px;
    }
    /* Product cards */
    .product-card {
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        box-shadow: 2px 2px 10px rgba(0, 0, 0, 0.1);
        background-color: white;
    }
    .product-card h4 {
        margin: 0 0 10px 0;
        font-size: 16px;
        color: #333;
    }
    .product-card p {
        margin: 5px 0;
        font-size: 14px;
        color: #555;
    }
    .product-card img {
        border-radius: 10px;
        margin-top: 10px;
    }
    .availability-available {
        color: #28a745;
        font-weight: bold;
    }
    .availability-out-of-stock {
        color: #dc3545;
        font-weight: bold;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Sticky title
st.markdown("<div class='sticky-title'><h1>Product Search Chat</h1></div>", unsafe_allow_html=True)

# Initialize session state for chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Chat history container
with st.container():
    st.markdown("<div class='chat-history'>", unsafe_allow_html=True)
    for message in st.session_state.chat_history:
        if message["role"] == "user":
            st.markdown(f"<div class='user-message'><b>You:</b> {message['content']}</div>", unsafe_allow_html=True)
        elif message["role"] == "bot":
            st.markdown(f"<div class='bot-message'><b>Bot:</b> {message['content']}</div>", unsafe_allow_html=True)
            if "products" in message and message["products"]:
                for product in message["products"]:
                    availability_class = "availability-available" if product["availability"] else "availability-out-of-stock"
                    availability_text = "Available" if product["availability"] else "Out of stock"
                    with st.expander(f"📦 {product['name']}", expanded=True):
                        st.markdown(
                            f"""
                            <div class="product-card">
                                <h4>{product['name']}</h4>
                                <p><b>Color:</b> {product['color']}</p>
                                <p><b>Availability:</b> <span class="{availability_class}">{availability_text}</span></p>
                            """,
                            unsafe_allow_html=True,
                        )
                        if product.get("image_url"):  # Display image if available
                            st.image(product["image_url"], width=200)
                        else:
                            st.write("**Image:** Not available")
    st.markdown("</div>", unsafe_allow_html=True)

# Sticky input container
st.markdown("<div class='sticky-input'>", unsafe_allow_html=True)
user_query = st.text_input("Enter your query (e.g., 'Show me red and black shirts'):", key="user_input", value="")
if st.button("Send"):
    if user_query.strip():
        # Add user query to chat history
        st.session_state.chat_history.append({"role": "user", "content": user_query})

        # Handle the query with a spinner
        with st.spinner("Processing..."):
            try:
                # Send the query to the FastAPI backend
                response = requests.post(
                    f"{FASTAPI_URL}/search",
                    json={"query": user_query}
                )
                if response.status_code == 200:
                    results = response.json()
                    st.session_state.chat_history.append({
                        "role": "bot",
                        "content": results["message"],
                        "products": results.get("products", [])
                    })
                else:
                    st.session_state.chat_history.append({
                        "role": "bot",
                        "content": f"Error: {response.status_code} - {response.text}"
                    })
            except requests.RequestException as e:
                st.session_state.chat_history.append({
                    "role": "bot",
                    "content": f"An error occurred: {e}"
                })

        # Clear the input field and refresh
        user_query = ""
        st.experimental_rerun()
    else:
        st.warning("Please enter a query before sending.")
st.markdown("</div>", unsafe_allow_html=True)
