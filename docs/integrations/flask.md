# Flask Integration

Integrate KnowledgeBeast with Flask applications.

## Basic Integration

```python
from flask import Flask, request, jsonify
from knowledgebeast import KnowledgeBeast

app = Flask(__name__)
kb = KnowledgeBeast()

@app.route('/search')
def search():
    query = request.args.get('q', '')
    n_results = int(request.args.get('n', 5))

    try:
        results = kb.query(query, n_results=n_results)
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.teardown_appcontext
def cleanup(exception=None):
    kb.shutdown()

if __name__ == '__main__':
    app.run(debug=True)
```

## With Blueprint

```python
from flask import Blueprint, request, jsonify
from knowledgebeast import KnowledgeBeast

kb_bp = Blueprint('knowledge', __name__)
kb = KnowledgeBeast()

@kb_bp.route('/query', methods=['POST'])
def query():
    data = request.get_json()
    results = kb.query(data['query'])
    return jsonify({"results": results})
```

## Next Steps

- [Python API Guide](../guides/python-api.md)
