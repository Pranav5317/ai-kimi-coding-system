import flask
from flask import Flask, jsonify, request
from datetime import datetime

app = Flask(__name__)

# In-memory storage for users and orders (in a real app, this would be a database)
users = [
    {"id": 1, "name": "John Doe", "email": "john@example.com", "role": "admin"},
    {"id": 2, "name": "Jane Smith", "email": "jane@example.com", "role": "user"},
    {"id": 3, "name": "Bob Johnson", "email": "bob@example.com", "role": "user"}
]

orders = [
    {"id": 1, "user_id": 1, "product": "Laptop", "amount": 1200.00},
    {"id": 2, "user_id": 2, "product": "Mouse", "amount": 25.00},
    {"id": 3, "user_id": 1, "product": "Keyboard", "amount": 75.00}
]

# Helper function to find user by ID
def find_user_by_id(user_id):
    for user in users:
        if user["id"] == user_id:
            return user
    return None

# Helper function to get user count
def get_user_count():
    return len(users)

# Helper function to get order count and revenue
def get_order_stats():
    order_count = len(orders)
    total_revenue = sum(order["amount"] for order in orders)
    return order_count, total_revenue

# Health check endpoint
@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"})

# Get all users
@app.route("/users", methods=["GET"])
def get_users():
    try:
        return jsonify(users)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Create a new user
@app.route("/users", methods=["POST"])
def create_user():
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data or "name" not in data or "email" not in data or "role" not in data:
            return jsonify({"error": "Name, email, and role are required"}), 400
        
        # Validate email format (basic validation)
        if "@" not in data["email"]:
            return jsonify({"error": "Invalid email format"}), 400
        
        # Generate new user ID
        new_id = max([user["id"] for user in users]) + 1 if users else 1
        
        # Create new user
        new_user = {
            "id": new_id,
            "name": data["name"],
            "email": data["email"],
            "role": data["role"]
        }
        
        users.append(new_user)
        return jsonify(new_user), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Get dashboard statistics
@app.route("/stats", methods=["GET"])
def get_stats():
    try:
        user_count = get_user_count()
        order_count, total_revenue = get_order_stats()
        
        stats = {
            "user_count": user_count,
            "order_count": order_count,
            "revenue": total_revenue
        }
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Get data table information with filtering capabilities
@app.route("/data", methods=["GET"])
def get_data():
    try:
        # Get query parameters for filtering
        user_id = request.args.get("user_id")
        role = request.args.get("role")
        min_amount = request.args.get("min_amount")
        max_amount = request.args.get("max_amount")
        
        # Start with all orders
        filtered_orders = orders.copy()
        
        # Apply filters if provided
        if user_id:
            filtered_orders = [order for order in filtered_orders if order["user_id"] == int(user_id)]
        
        if role:
            # Filter users by role and then get their orders
            user_ids = [user["id"] for user in users if user["role"] == role]
            filtered_orders = [order for order in filtered_orders if order["user_id"] in user_ids]
        
        if min_amount:
            filtered_orders = [order for order in filtered_orders if order["amount"] >= float(min_amount)]
        
        if max_amount:
            filtered_orders = [order for order in filtered_orders if order["amount"] <= float(max_amount)]
        
        # Add user information to orders
        for order in filtered_orders:
            user = find_user_by_id(order["user_id"])
            if user:
                order["user_name"] = user["name"]
                order["user_email"] = user["email"]
        
        return jsonify({
            "data": filtered_orders,
            "count": len(filtered_orders)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Error handler for 404
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

# Error handler for 500
@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)