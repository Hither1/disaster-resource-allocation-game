from flask import Flask, render_template, request, jsonify
import crafter

app = Flask(__name__)
current_environment = None  # Initialize as None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_game', methods=['POST'])
def start_game():
    global current_environment
    config, _ = crafter.config.get_config()
    current_environment = crafter.Env(config)  # Create a new instance of your game environment
    return jsonify({'status': 'success', 'message': 'Game environment initialized successfully!'})

@app.route('/update_environment', methods=['POST'])
def update_environment():
    global current_environment
    if current_environment is None:
        return jsonify({'status': 'error', 'message': 'Game environment not initialized'})

    action = request.form.get('action')  # Get the action from the frontend

    # Call the corresponding method in your game logic
    if action == 'increase_score':
        current_environment.increase_score()
    elif action == 'decrease_score':
        current_environment.decrease_score()

    # You can return a response to the frontend if needed
    return jsonify({'status': 'success', 'message': 'Environment updated successfully!'})

if __name__ == '__main__':
    app.run(debug=True)