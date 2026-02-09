"""
NLP Recipe Generator using GPT-based architecture
Creates personalized recipes from available ingredients
"""
import torch
import torch.nn as nn
from transformers import GPT2LMHeadModel, GPT2Tokenizer
from typing import List, Dict
from .device_config import get_device, to_device

class NLPRecipeGenerator:
    """
    GPT-based recipe generator
    
    Input: Available ingredients + dietary constraints + cuisine preference
    Output: Novel recipe with name, ingredients, instructions
    
    Fine-tuned on RecipeDB corpus + user ratings
    """
    
    def __init__(self, model_name='gpt2', device=None):
        """Initialize with pretrained GPT-2"""
        # Set device
        self.device = device if device is not None else get_device()
        
        self.tokenizer = GPT2Tokenizer.from_pretrained(model_name)
        self.model = GPT2LMHeadModel.from_pretrained(model_name)
        
        # Add special tokens
        special_tokens = {
            'pad_token': '<PAD>',
            'additional_special_tokens': ['<RECIPE>', '<INGREDIENTS>', '<INSTRUCTIONS>', '<END>']
        }
        self.tokenizer.add_special_tokens(special_tokens)
        self.model.resize_token_embeddings(len(self.tokenizer))
        
        # Move model to device
        self.model = self.model.to(self.device)
        self.model.eval()
    
    def generate_recipe(self, 
                       ingredients: List[str],
                       dietary_constraints: List[str] = None,
                       cuisine: str = None,
                       max_length: int = 512) -> Dict[str, any]:
        """
        Generate a novel recipe
        
        Args:
            ingredients: Available ingredients
            dietary_constraints: e.g., ['vegan', 'gluten-free']
            cuisine: e.g., 'Italian', 'Mexican', 'Asian'
            max_length: Maximum tokens to generate
        
        Returns:
            {
                'name': str,
                'ingredients': List[str],
                'instructions': List[str],
                'estimated_time': int (minutes),
                'difficulty': str
            }
        """
        # Construct prompt
        prompt = self._construct_prompt(ingredients, dietary_constraints, cuisine)
        
        # Tokenize
        input_ids = self.tokenizer.encode(prompt, return_tensors='pt').to(self.device)
        
        # Generate
        with torch.no_grad():
            output = self.model.generate(
                input_ids,
                max_length=max_length,
                num_return_sequences=1,
                temperature=0.8,
                top_k=50,
                top_p=0.95,
                do_sample=True,
                pad_token_id=self.tokenizer.pad_token_id
            )
        
        # Decode
        generated_text = self.tokenizer.decode(output[0], skip_special_tokens=False)
        
        # Parse recipe
        recipe = self._parse_generated_recipe(generated_text)
        
        return recipe
    
    def _construct_prompt(self, ingredients, dietary_constraints, cuisine):
        """Construct GPT prompt"""
        prompt = "<RECIPE>\n"
        
        if cuisine:
            prompt += f"Cuisine: {cuisine}\n"
        
        if dietary_constraints:
            prompt += f"Dietary: {', '.join(dietary_constraints)}\n"
        
        prompt += f"Available Ingredients: {', '.join(ingredients)}\n\n"
        prompt += "Recipe Name: "
        
        return prompt
    
    def _parse_generated_recipe(self, text: str) -> Dict:
        """Parse generated text into structured recipe"""
        lines = text.split('\n')
        
        recipe = {
            'name': 'Generated Recipe',
            'ingredients': [],
            'instructions': [],
            'estimated_time': 30,
            'difficulty': 'Medium'
        }
        
        current_section = None
        
        for line in lines:
            line = line.strip()
            
            if 'Recipe Name:' in line:
                recipe['name'] = line.split('Recipe Name:')[-1].strip()
            elif '<INGREDIENTS>' in line or 'Ingredients:' in line:
                current_section = 'ingredients'
            elif '<INSTRUCTIONS>' in line or 'Instructions:' in line:
                current_section = 'instructions'
            elif '<END>' in line:
                break
            elif line and current_section == 'ingredients':
                # Clean ingredient line
                ingredient = line.lstrip('- •*0123456789. ')
                if ingredient:
                    recipe['ingredients'].append(ingredient)
            elif line and current_section == 'instructions':
                # Clean instruction line
                instruction = line.lstrip('0123456789. ')
                if instruction:
                    recipe['instructions'].append(instruction)
        
        return recipe
    
    def generate_variations(self, base_recipe: Dict, num_variations: int = 3) -> List[Dict]:
        """Generate variations of a base recipe"""
        variations = []
        
        for i in range(num_variations):
            # Modify prompt slightly for variation
            ingredients = base_recipe.get('ingredients', [])
            
            # Add variation instruction
            prompt = f"Create a variation of this recipe:\n"
            prompt += f"Original: {base_recipe.get('name', 'Recipe')}\n"
            prompt += f"Ingredients: {', '.join(ingredients[:5])}\n"
            prompt += f"Make it more {'spicy' if i == 0 else 'healthy' if i == 1 else 'quick'}\n\n"
            prompt += "New Recipe Name: "
            
            input_ids = self.tokenizer.encode(prompt, return_tensors='pt').to(self.device)
            
            with torch.no_grad():
                output = self.model.generate(
                    input_ids,
                    max_length=512,
                    temperature=0.9 + i * 0.1,  # Vary temperature
                    top_k=50,
                    top_p=0.95,
                    do_sample=True
                )
            
            generated = self.tokenizer.decode(output[0], skip_special_tokens=True)
            variation = self._parse_generated_recipe(generated)
            variations.append(variation)
        
        return variations
    
    def suggest_substitutions(self, ingredient: str, dietary_constraint: str = None) -> List[str]:
        """Suggest ingredient substitutions"""
        prompt = f"Suggest 3 substitutes for {ingredient}"
        if dietary_constraint:
            prompt += f" that are {dietary_constraint}"
        prompt += ":\n1. "
        
        input_ids = self.tokenizer.encode(prompt, return_tensors='pt').to(self.device)
        
        with torch.no_grad():
            output = self.model.generate(
                input_ids,
                max_length=100,
                temperature=0.7,
                top_k=40,
                do_sample=True
            )
        
        generated = self.tokenizer.decode(output[0], skip_special_tokens=True)
        
        # Parse substitutions
        substitutions = []
        for line in generated.split('\n'):
            line = line.strip().lstrip('0123456789. -')
            if line and len(line) < 50:
                substitutions.append(line)
        
        return substitutions[:3]
