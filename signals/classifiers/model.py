import os
import torch
import torch.nn as nn
from transformers import DistilBertTokenizer, DistilBertForSequenceClassification

MODEL_NAME = "distilbert-base-uncased"

def get_tokenizer():
    """Returns the standard DistilBERT tokenizer."""
    return DistilBertTokenizer.from_pretrained(MODEL_NAME)

def get_model():
    """Returns a DistilBERT model for binary classification."""
    return DistilBertForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2)
