"""Project templates for quick setup.

This module provides pre-configured project templates for common use cases.
Each template includes:
- Optimized embedding model and chunking configuration
- Sample documents for testing
- Appropriate metadata structure

Available Templates:
- ai-research: Technical AI/ML papers and documentation
- code-search: Code repositories and technical docs
- documentation: Product documentation and user guides
- support-kb: Customer support Q&A database
"""

from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

__all__ = ['TEMPLATES', 'ProjectTemplateManager']


TEMPLATES = {
    "ai-research": {
        "name": "AI Research Project",
        "description": "Optimized for AI/ML research papers and technical articles",
        "config": {
            "embedding_model": "all-mpnet-base-v2",  # Higher quality for technical content
            "chunk_size": 512,
            "chunk_overlap": 50,
        },
        "sample_docs": [
            {
                "content": """Attention Is All You Need

The dominant sequence transduction models are based on complex recurrent or
convolutional neural networks that include an encoder and a decoder. The best
performing models also connect the encoder and decoder through an attention
mechanism. We propose a new simple network architecture, the Transformer,
based solely on attention mechanisms, dispensing with recurrence and convolutions
entirely.

The Transformer allows for significantly more parallelization and can reach a new
state of the art in translation quality after being trained for as little as twelve hours
on eight P100 GPUs.""",
                "metadata": {"topic": "transformers", "type": "paper", "year": 2017, "authors": "Vaswani et al."}
            },
            {
                "content": """BERT: Pre-training of Deep Bidirectional Transformers

We introduce a new language representation model called BERT, which stands for
Bidirectional Encoder Representations from Transformers. Unlike recent language
representation models, BERT is designed to pre-train deep bidirectional
representations from unlabeled text by jointly conditioning on both left and
right context in all layers.

BERT is conceptually simple and empirically powerful. It obtains new state-of-the-art
results on eleven natural language processing tasks, including pushing the GLUE score
to 80.5% (7.7% point absolute improvement), MultiNLI accuracy to 86.7% (4.6% absolute
improvement), SQuAD v1.1 question answering Test F1 to 93.2 (1.5 point absolute
improvement).""",
                "metadata": {"topic": "nlp", "type": "paper", "year": 2018, "authors": "Devlin et al."}
            },
            {
                "content": """GPT-3: Language Models are Few-Shot Learners

Recent work has demonstrated substantial gains on many NLP tasks and benchmarks
by pre-training on a large corpus of text followed by fine-tuning on a specific
task. While typically task-agnostic in architecture, this method still requires
task-specific fine-tuning datasets of thousands or tens of thousands of examples.

Here we show that scaling up language models greatly improves task-agnostic,
few-shot performance, sometimes even becoming competitive with prior state-of-the-art
fine-tuning approaches. GPT-3, an autoregressive language model with 175 billion
parameters, achieves strong performance on many NLP datasets, including translation,
question-answering, and cloze tasks.""",
                "metadata": {"topic": "language-models", "type": "paper", "year": 2020, "authors": "Brown et al."}
            }
        ]
    },

    "code-search": {
        "name": "Code Search Project",
        "description": "Optimized for searching code repositories and technical documentation",
        "config": {
            "embedding_model": "all-MiniLM-L6-v2",  # Fast for code
            "chunk_size": 256,
            "chunk_overlap": 30,
        },
        "sample_docs": [
            {
                "content": """def binary_search(arr, target):
    '''Binary search algorithm implementation.

    Time Complexity: O(log n)
    Space Complexity: O(1)

    Args:
        arr: Sorted array to search
        target: Value to find

    Returns:
        Index of target if found, -1 otherwise

    Example:
        >>> binary_search([1, 2, 3, 4, 5], 3)
        2
        >>> binary_search([1, 2, 3, 4, 5], 6)
        -1
    '''
    left, right = 0, len(arr) - 1

    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1

    return -1""",
                "metadata": {"language": "python", "type": "function", "algorithm": "search", "complexity": "O(log n)"}
            },
            {
                "content": """class BinaryTree:
    '''Binary tree data structure implementation.

    Provides methods for insertion, traversal, and search operations.
    '''

    def __init__(self, value):
        '''Initialize binary tree node.

        Args:
            value: Value to store in node
        '''
        self.value = value
        self.left = None
        self.right = None

    def insert(self, value):
        '''Insert value into binary tree.

        Maintains binary tree property:
        - Left child < parent
        - Right child >= parent

        Args:
            value: Value to insert
        '''
        if value < self.value:
            if self.left is None:
                self.left = BinaryTree(value)
            else:
                self.left.insert(value)
        else:
            if self.right is None:
                self.right = BinaryTree(value)
            else:
                self.right.insert(value)

    def search(self, value):
        '''Search for value in tree.

        Returns:
            True if value found, False otherwise
        '''
        if value == self.value:
            return True
        elif value < self.value and self.left:
            return self.left.search(value)
        elif value >= self.value and self.right:
            return self.right.search(value)
        return False""",
                "metadata": {"language": "python", "type": "class", "data_structure": "tree", "complexity": "O(log n)"}
            },
            {
                "content": """function quickSort(arr) {
    /**
     * Quick sort algorithm implementation
     *
     * Time Complexity: O(n log n) average, O(n^2) worst
     * Space Complexity: O(log n)
     *
     * @param {Array} arr - Array to sort
     * @returns {Array} Sorted array
     */
    if (arr.length <= 1) return arr;

    const pivot = arr[Math.floor(arr.length / 2)];
    const left = arr.filter(x => x < pivot);
    const middle = arr.filter(x => x === pivot);
    const right = arr.filter(x => x > pivot);

    return [...quickSort(left), ...middle, ...quickSort(right)];
}

// Example usage
const unsorted = [3, 6, 8, 10, 1, 2, 1];
console.log(quickSort(unsorted)); // [1, 1, 2, 3, 6, 8, 10]""",
                "metadata": {"language": "javascript", "type": "function", "algorithm": "sorting", "complexity": "O(n log n)"}
            }
        ]
    },

    "documentation": {
        "name": "Documentation Project",
        "description": "Optimized for product documentation and user guides",
        "config": {
            "embedding_model": "all-MiniLM-L6-v2",
            "chunk_size": 384,
            "chunk_overlap": 40,
        },
        "sample_docs": [
            {
                "content": """Getting Started Guide

Welcome to KnowledgeBeast! This guide will help you get up and running in minutes.

Installation
============

Install via pip:
```bash
pip install knowledgebeast
```

Or using Docker:
```bash
docker pull knowledgebeast/knowledgebeast:latest
docker run -p 8000:8000 knowledgebeast/knowledgebeast:latest
```

Quick Start
===========

1. Set up your API key:
   ```bash
   export KB_API_KEY=your-secret-key
   ```

2. Start the server:
   ```bash
   knowledgebeast serve
   ```

3. Create your first project:
   ```bash
   curl -X POST http://localhost:8000/api/v2/projects \\
     -H "X-API-Key: your-secret-key" \\
     -H "Content-Type: application/json" \\
     -d '{"name": "My First Project", "description": "Test project"}'
   ```

4. Ingest documents:
   ```bash
   curl -X POST http://localhost:8000/api/v2/{project_id}/ingest \\
     -H "X-API-Key: your-secret-key" \\
     -H "Content-Type: application/json" \\
     -d '{"content": "Your document content here"}'
   ```

5. Query your knowledge:
   ```bash
   curl -X POST http://localhost:8000/api/v2/{project_id}/query \\
     -H "X-API-Key: your-secret-key" \\
     -H "Content-Type: application/json" \\
     -d '{"query": "your search query"}'
   ```

Next Steps
==========

- Read the [API Reference](/docs/api)
- Learn about [Project Templates](/docs/templates)
- Explore [Advanced Features](/docs/advanced)""",
                "metadata": {"section": "getting-started", "type": "guide", "difficulty": "beginner"}
            },
            {
                "content": """API Authentication

KnowledgeBeast uses API key authentication to secure all endpoints.

Obtaining an API Key
====================

API keys can be generated from the dashboard or using the CLI:

```bash
knowledgebeast api-key create --name "My Application"
```

Using API Keys
==============

Include your API key in the X-API-Key header:

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/v2/projects
```

Or in Python:
```python
import requests

headers = {
    "X-API-Key": "your-api-key",
    "Content-Type": "application/json"
}

response = requests.get(
    "http://localhost:8000/api/v2/projects",
    headers=headers
)
```

Rate Limiting
=============

API keys are subject to rate limiting:
- 100 requests per minute for read operations
- 20 requests per minute for write operations
- 5 requests per minute for export/import operations

Rate limit information is included in response headers:
- X-RateLimit-Limit: Maximum requests per window
- X-RateLimit-Remaining: Remaining requests
- X-RateLimit-Reset: Timestamp when limit resets

Best Practices
==============

1. Store API keys securely (environment variables, secrets manager)
2. Use different keys for different applications
3. Rotate keys regularly
4. Never commit keys to version control""",
                "metadata": {"section": "authentication", "type": "guide", "difficulty": "beginner"}
            }
        ]
    },

    "support-kb": {
        "name": "Support Knowledge Base",
        "description": "Optimized for customer support Q&A and troubleshooting",
        "config": {
            "embedding_model": "all-MiniLM-L6-v2",
            "chunk_size": 256,
            "chunk_overlap": 20,
        },
        "sample_docs": [
            {
                "content": """Q: How do I reset my password?

A: To reset your password:

1. Go to the login page (https://app.example.com/login)
2. Click the "Forgot Password?" link below the login form
3. Enter your registered email address
4. Click "Send Reset Link"
5. Check your email inbox (and spam folder) for the reset link
6. Click the link in the email
7. Enter your new password (must be at least 8 characters)
8. Confirm your new password
9. Click "Reset Password"

If you don't receive the email within 5 minutes:
- Check your spam/junk folder
- Verify you entered the correct email address
- Contact support if the issue persists

Related Topics:
- Updating your account email
- Account security best practices
- Two-factor authentication""",
                "metadata": {"category": "account", "type": "faq", "priority": "high", "tags": ["password", "login", "security"]}
            },
            {
                "content": """Q: Why is my upload failing?

A: File uploads may fail for several reasons. Here are the most common issues and solutions:

File Size Too Large
-------------------
Maximum file size: 100MB
Solution: Compress your file or split into smaller parts

Unsupported File Type
---------------------
Supported formats: .pdf, .docx, .txt, .md, .html
Solution: Convert your file to a supported format

Network Timeout
---------------
Large files may timeout on slow connections
Solution:
1. Check your internet connection
2. Try uploading during off-peak hours
3. Use a wired connection instead of WiFi

Browser Issues
--------------
Clear browser cache and cookies
Solution:
1. Clear your browser cache (Ctrl+Shift+Delete)
2. Try a different browser
3. Disable browser extensions temporarily

Still Having Issues?
--------------------
Contact support with:
- File name and size
- File format
- Browser and version
- Error message (if any)
- Screenshot of the error""",
                "metadata": {"category": "technical", "type": "faq", "priority": "medium", "tags": ["upload", "error", "troubleshooting"]}
            },
            {
                "content": """Q: How do I cancel my subscription?

A: We're sorry to see you go! Here's how to cancel your subscription:

Steps to Cancel
===============

1. Log into your account
2. Click your profile icon (top right)
3. Select "Billing & Subscription"
4. Click "Manage Subscription"
5. Click "Cancel Subscription"
6. Select a cancellation reason (optional but helpful)
7. Click "Confirm Cancellation"

What Happens After Cancellation?
=================================

- Your account remains active until the end of the current billing period
- You can continue using all features until then
- No further charges will be made
- Your data will be retained for 30 days after cancellation
- You can reactivate anytime during the 30-day grace period

Billing Refunds
===============

- Monthly plans: No refunds (you keep access until period ends)
- Annual plans: Pro-rated refund available (contact support)
- Enterprise plans: Per contract terms

Before You Cancel
=================

Consider these alternatives:
- Downgrade to a lower-tier plan
- Pause your subscription (Premium/Enterprise only)
- Contact support for assistance

Need Help?
==========

Contact support@example.com if you:
- Want to discuss cancellation
- Need a refund
- Have technical issues
- Want to provide feedback""",
                "metadata": {"category": "billing", "type": "faq", "priority": "high", "tags": ["subscription", "cancel", "refund"]}
            }
        ]
    }
}


class ProjectTemplateManager:
    """Manage project templates for quick setup."""

    @staticmethod
    def create_from_template(
        template_name: str,
        project_name: str,
        pm,
        include_samples: bool = True
    ) -> str:
        """Create project from template.

        Args:
            template_name: Name of template to use (ai-research, code-search, etc.)
            project_name: Name for new project
            pm: ProjectManager instance
            include_samples: If True, ingest sample documents

        Returns:
            project_id: ID of created project

        Raises:
            ValueError: If template not found

        Example:
            >>> from knowledgebeast.core.project_manager import ProjectManager
            >>> from knowledgebeast.templates import ProjectTemplateManager
            >>>
            >>> pm = ProjectManager()
            >>> project_id = ProjectTemplateManager.create_from_template(
            ...     "ai-research",
            ...     "My AI Research Project",
            ...     pm,
            ...     include_samples=True
            ... )
            >>> print(f"Created project: {project_id}")
        """
        if template_name not in TEMPLATES:
            available = ", ".join(TEMPLATES.keys())
            raise ValueError(f"Unknown template: {template_name}. Available: {available}")

        template = TEMPLATES[template_name]

        logger.info(f"Creating project from template '{template_name}': {project_name}")

        # Create project with template config
        project = pm.create_project(
            name=project_name,
            description=template['description'],
            embedding_model=template['config']['embedding_model'],
            metadata={
                'template': template_name,
                'template_config': template['config']
            }
        )

        # Ingest sample documents if requested
        if include_samples:
            logger.info(f"Ingesting {len(template['sample_docs'])} sample documents")
            collection = pm.get_project_collection(project.project_id)

            for idx, doc in enumerate(template['sample_docs']):
                doc_id = f"{template_name}_sample_{idx}"
                collection.add(
                    ids=[doc_id],
                    documents=[doc['content']],
                    metadatas=[{
                        **doc['metadata'],
                        'template_sample': True
                    }]
                )

            logger.info(f"Successfully created project with {len(template['sample_docs'])} sample documents")
        else:
            logger.info("Project created without sample documents")

        return project.project_id

    @staticmethod
    def list_templates() -> List[Dict[str, Any]]:
        """List all available templates.

        Returns:
            List of template metadata dictionaries

        Example:
            >>> templates = ProjectTemplateManager.list_templates()
            >>> for template in templates:
            ...     print(f"{template['name']}: {template['description']}")
        """
        return [
            {
                "name": name,
                "display_name": tmpl['name'],
                "description": tmpl['description'],
                "config": tmpl['config'],
                "sample_count": len(tmpl['sample_docs'])
            }
            for name, tmpl in TEMPLATES.items()
        ]

    @staticmethod
    def get_template(template_name: str) -> Dict[str, Any]:
        """Get template details.

        Args:
            template_name: Template identifier

        Returns:
            Template configuration dictionary

        Raises:
            ValueError: If template not found

        Example:
            >>> template = ProjectTemplateManager.get_template("ai-research")
            >>> print(template['description'])
            'Optimized for AI/ML research papers and technical articles'
        """
        if template_name not in TEMPLATES:
            available = ", ".join(TEMPLATES.keys())
            raise ValueError(f"Unknown template: {template_name}. Available: {available}")
        return TEMPLATES[template_name]
