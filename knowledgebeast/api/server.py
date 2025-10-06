"""REST API server for KnowledgeBeast."""

from typing import Optional


def start_server(config, host: str = 'localhost', port: int = 5000, debug: bool = False):
    """Start the Flask API server."""
    try:
        from flask import Flask, jsonify, request
    except ImportError:
        raise ImportError("Flask is required for the API server. Install with: pip install flask")

    from knowledgebeast.core.engine import KnowledgeBase

    app = Flask(__name__)
    kb = KnowledgeBase.from_config(config)

    @app.route('/health', methods=['GET'])
    def health():
        """Health check endpoint."""
        return jsonify({
            'status': 'healthy',
            'service': 'KnowledgeBeast',
            'version': '0.1.0',
        })

    @app.route('/query', methods=['POST'])
    def query():
        """Query endpoint."""
        data = request.get_json()
        search_terms = data.get('query', '')
        limit = data.get('limit', 10)

        results = kb.query(search_terms, limit=limit)

        return jsonify({
            'query': search_terms,
            'results': results,
            'count': len(results),
        })

    @app.route('/stats', methods=['GET'])
    def stats():
        """Statistics endpoint."""
        return jsonify(kb.get_stats())

    @app.route('/documents/add', methods=['POST'])
    def add_document():
        """Add document endpoint."""
        data = request.get_json()
        file_path = data.get('path', '')

        try:
            kb.add_document(file_path)
            return jsonify({
                'status': 'success',
                'message': f'Document added: {file_path}',
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': str(e),
            }), 400

    app.run(host=host, port=port, debug=debug)
