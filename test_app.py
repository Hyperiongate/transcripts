"""
Simple test app to verify Flask is working
"""
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return """
    <html>
    <head><title>Fact Checker Test</title></head>
    <body>
        <h1>Fact Checker Test Page</h1>
        <p>If you can see this, Flask is working!</p>
        <p>Check these endpoints:</p>
        <ul>
            <li><a href="/health">/health</a> - Health check</li>
            <li><a href="/test">/test</a> - Test endpoint</li>
        </ul>
    </body>
    </html>
    """

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'message': 'Flask is running'
    })

@app.route('/test')
def test():
    return jsonify({
        'message': 'Test endpoint working',
        'timestamp': '2024-01-20'
    })

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 10000))
    print(f"Starting test app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)
