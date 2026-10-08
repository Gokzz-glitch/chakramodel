"""
Notebook Generation Script for Worker 3:
Combos #5 (Fed-ChakraNet) and #6 (ChakraTransformer)
"""
import json
import ast
import os
import sys
from pathlib import Path

def make_notebook(cells):
    return {
        "nbformat": 4,
        "nbformat_minor": 4,
        "metadata": {
            "kernelspec": {
                "name": "python3",
                "display_name": "Python 3 (ipykernel)"
            },
            "language_info": {
                "name": "python",
                "version": "3.10.12",
                "mimetype": "text/x-python",
                "codemirror_mode": {"name": "ipython", "version": 3},
                "pygments_lexer": "ipython3",
                "nbconvert_exporter": "python",
                "file_extension": ".py"
            },
            "accelerator": "GPU"
        },
        "cells": cells
    }

def markdown_cell(source_text, cell_id=None):
    cell = {
        "cell_type": "markdown",
        "metadata": {},
        "source": [line + "\n" for line in source_text.splitlines()]
    }
    if cell_id:
        cell["metadata"]["id"] = cell_id
    return cell

def code_cell(source_text, cell_id=None):
    cell = {
        "cell_type": "code",
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": [line + "\n" for line in source_text.splitlines()]
    }
    if cell_id:
        cell["metadata"]["id"] = cell_id
    return cell

print("Helper definitions loaded.")
