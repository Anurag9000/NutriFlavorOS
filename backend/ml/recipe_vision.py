"""
Computer Vision Recipe Analyzer using ResNet50
Analyzes food photos to estimate nutrition and log meals effortlessly
"""
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as transforms
from PIL import Image
import numpy as np
from typing import Dict, Tuple
from .device_config import get_device, to_device

class RecipeVisionAnalyzer(nn.Module):
    """
    Computer Vision model for meal logging via photos
    
    Architecture: ResNet50 backbone + Nutrition Regression Head
    Input: Food photo (224x224 RGB)
    Output: Calorie estimate + macro breakdown (protein, carbs, fat)
    
    Training: Food-101 dataset + nutrition labels
    """
    
    def __init__(self, num_classes=101, pretrained=True, device=None):
        super().__init__()
        
        # Set device
        self.device = device if device is not None else get_device()
        
        # Load pretrained ResNet50
        self.backbone = models.resnet50(pretrained=pretrained)
        
        # Remove final FC layer
        num_features = self.backbone.fc.in_features
        self.backbone.fc = nn.Identity()
        
        # Food classification head
        self.classifier = nn.Linear(num_features, num_classes)
        
        # Nutrition regression head
        self.nutrition_head = nn.Sequential(
            nn.Linear(num_features, 512),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 4)  # [calories, protein_g, carbs_g, fat_g]
        )
        
        # Image preprocessing
        self.transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])
        
        # Move model to device
        self.to(self.device)
    
    def forward(self, x):
        """
        Args:
            x: (batch, 3, 224, 224) - RGB images
        
        Returns:
            food_class: (batch, num_classes) - Food classification logits
            nutrition: (batch, 4) - [calories, protein, carbs, fat]
        """
        # Extract features
        features = self.backbone(x)
        
        # Classification
        food_class = self.classifier(features)
        
        # Nutrition estimation
        nutrition = self.nutrition_head(features)
        
        # Ensure positive values for nutrition
        nutrition = torch.relu(nutrition)
        
        return food_class, nutrition
    
    def analyze_image(self, image_path: str) -> Dict[str, any]:
        """
        Analyze a food image and return nutrition estimates
        
        Args:
            image_path: Path to food image
        
        Returns:
            {
                'food_name': str,
                'confidence': float,
                'calories': int,
                'protein_g': int,
                'carbs_g': int,
                'fat_g': int
            }
        """
        self.eval()
        
        # Load and preprocess image
        image = Image.open(image_path).convert('RGB')
        image_tensor = self.transform(image).unsqueeze(0)
        
        # Move to device
        image_tensor = image_tensor.to(self.device)
        
        with torch.no_grad():
            food_class, nutrition = self.forward(image_tensor)
        
        # Get predicted food class
        probs = torch.softmax(food_class, dim=1)
        confidence, predicted_class = torch.max(probs, dim=1)
        
        # Food-101 class names (simplified)
        food_names = [
            "apple_pie", "baby_back_ribs", "baklava", "beef_carpaccio", "beef_tartare",
            "beet_salad", "beignets", "bibimbap", "bread_pudding", "breakfast_burrito",
            "bruschetta", "caesar_salad", "cannoli", "caprese_salad", "carrot_cake",
            "ceviche", "cheesecake", "cheese_plate", "chicken_curry", "chicken_quesadilla",
            "chicken_wings", "chocolate_cake", "chocolate_mousse", "churros", "clam_chowder",
            "club_sandwich", "crab_cakes", "creme_brulee", "croque_madame", "cup_cakes",
            "deviled_eggs", "donuts", "dumplings", "edamame", "eggs_benedict",
            "escargots", "falafel", "filet_mignon", "fish_and_chips", "foie_gras",
            "french_fries", "french_onion_soup", "french_toast", "fried_calamari", "fried_rice",
            "frozen_yogurt", "garlic_bread", "gnocchi", "greek_salad", "grilled_cheese_sandwich",
            "grilled_salmon", "guacamole", "gyoza", "hamburger", "hot_and_sour_soup",
            "hot_dog", "huevos_rancheros", "hummus", "ice_cream", "lasagna",
            "lobster_bisque", "lobster_roll_sandwich", "macaroni_and_cheese", "macarons", "miso_soup",
            "mussels", "nachos", "omelette", "onion_rings", "oysters",
            "pad_thai", "paella", "pancakes", "panna_cotta", "peking_duck",
            "pho", "pizza", "pork_chop", "poutine", "prime_rib",
            "pulled_pork_sandwich", "ramen", "ravioli", "red_velvet_cake", "risotto",
            "samosa", "sashimi", "scallops", "seaweed_salad", "shrimp_and_grits",
            "spaghetti_bolognese", "spaghetti_carbonara", "spring_rolls", "steak", "strawberry_shortcake",
            "sushi", "tacos", "takoyaki", "tiramisu", "tuna_tartare", "waffles"
        ]
        
        food_name = food_names[predicted_class.item()] if predicted_class.item() < len(food_names) else "unknown"
        
        # Extract nutrition values
        calories = int(nutrition[0, 0].item())
        protein = int(nutrition[0, 1].item())
        carbs = int(nutrition[0, 2].item())
        fat = int(nutrition[0, 3].item())
        
        return {
            'food_name': food_name.replace('_', ' ').title(),
            'confidence': confidence.item(),
            'calories': calories,
            'protein_g': protein,
            'carbs_g': carbs,
            'fat_g': fat
        }
    
    def batch_analyze(self, image_paths: list) -> list:
        """Analyze multiple images in batch"""
        results = []
        for path in image_paths:
            try:
                result = self.analyze_image(path)
                results.append(result)
            except Exception as e:
                results.append({'error': str(e)})
        return results
