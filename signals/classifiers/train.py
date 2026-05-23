import os
import argparse
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import AdamW
from signals.classifiers.model import get_tokenizer, get_model
from common.config import settings

# Labeled data for training
TRAINING_DATA = {
    "refusal": {
        "pos": [
            "I cannot fulfill this request.",
            "As an AI language model, I am unable to answer.",
            "Sorry, but I cannot perform this action.",
            "I am sorry, but I am unable to help you with that.",
            "Unfortunately, I cannot complete this step."
        ],
        "neg": [
            "SRM check completed successfully.",
            "ATE is 2.4% with p-value 0.003.",
            "Input validated and randomization is intact.",
            "Drafting the stakeholder recommendation memo.",
            "CUPED variance reduction was applied."
        ]
    },
    "task_failure": {
        "pos": [
            "Fatal exception occurred during run.",
            "Failed to parse the database output.",
            "Traceback: KeyError in handler line 54.",
            "Invalid format encountered in input payload.",
            "Runtime error: division by zero in variance calculation."
        ],
        "neg": [
            "The data was successfully randomized.",
            "Lift estimate is positive and significant.",
            "Completed step 1 successfully.",
            "SRM p-value: 0.69 (stable randomization).",
            "Everything is running clean."
        ]
    },
    "low_confidence_output": {
        "pos": [
            "The result has extremely high variance.",
            "I am not sure about this estimation.",
            "unreliable results due to low sample size.",
            "The computed effect estimate is possibly incorrect.",
            "The ATE value is out of plausible bounds."
        ],
        "neg": [
            "Highly significant lift observed.",
            "The result is statistically solid.",
            "SRM validation checks passed completely.",
            "ATE estimate is robust and ready.",
            "Confidence interval is narrow and significant."
        ]
    },
    "malformed_handoff": {
        "pos": [
            "Missing required key in pipeline handoff.",
            "Malformed input state received.",
            "Handoff failed from step 1 to step 2.",
            "Invalid transition format detected.",
            "State object does not contain valid output fields."
        ],
        "neg": [
            "Handoff completed via sequential memory.",
            "Successfully forwarded the output data.",
            "Step 2 received clean state payload.",
            "Input from preceding step received via mesh.",
            "Randomization checks are verified."
        ]
    }
}

class FailureDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_len=64):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = self.texts[idx]
        label = self.labels[idx]
        encoding = self.tokenizer(
            text,
            add_special_tokens=True,
            max_length=self.max_len,
            padding="max_length",
            truncation=True,
            return_tensors="pt"
        )
        return {
            "input_ids": encoding["input_ids"].flatten(),
            "attention_mask": encoding["attention_mask"].flatten(),
            "labels": torch.tensor(label, dtype=torch.long)
        }

def train_classifier(kind: str, save_dir: str, quick: bool = False):
    """Trains a DistilBERT model for a specific failure kind."""
    print(f"--- Training classifier for '{kind}' ---")
    pos_texts = TRAINING_DATA[kind]["pos"]
    neg_texts = TRAINING_DATA[kind]["neg"]
    
    texts = pos_texts + neg_texts
    labels = [1] * len(pos_texts) + [0] * len(neg_texts)
    
    tokenizer = get_tokenizer()
    model = get_model()
    
    dataset = FailureDataset(texts, labels, tokenizer)
    dataloader = DataLoader(dataset, batch_size=2, shuffle=True)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    
    optimizer = AdamW(model.parameters(), lr=5e-5)
    model.train()
    
    epochs = 1 if quick else 3
    for epoch in range(epochs):
        total_loss = 0
        for batch in dataloader:
            optimizer.zero_grad()
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)
            
            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels
            )
            loss = outputs.loss
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            
            if quick:
                break # Only run 1 step in quick mode
                
        print(f"Epoch {epoch + 1}/{epochs} | Loss: {total_loss:.4f}")
        
    # Save the model
    os.makedirs(save_dir, exist_ok=True)
    model.save_pretrained(save_dir)
    tokenizer.save_pretrained(save_dir)
    print(f"Saved classifier for '{kind}' to {save_dir}")

def train_all(quick: bool = False):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    saved_models_dir = os.path.join(base_dir, "saved_models")
    
    for kind in TRAINING_DATA.keys():
        save_path = os.path.join(saved_models_dir, kind)
        if settings.mock or quick:
            # Under mock or quick mode, we write a dummy model file (or mock directory) to save time/resources
            os.makedirs(save_path, exist_ok=True)
            with open(os.path.join(save_path, "dummy.txt"), "w") as f:
                f.write("mock_classifier_model")
            print(f"Skipping DL training. Created mock placeholder at {save_path}")
        else:
            train_classifier(kind, save_path, quick=quick)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Run quick 1-step training")
    args = parser.parse_args()
    
    train_all(quick=args.quick)
