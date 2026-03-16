import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

def generate_product_images():
    load_dotenv()
    
    # Verify API key
    if "GEMINI_API_KEY" not in os.environ:
        print("Error: GEMINI_API_KEY environment variable not set.")
        return

    # Load product data
    products_file = 'data/products.json'
    if not os.path.exists(products_file):
        print(f"Error: {products_file} not found. Run extract_products.py first.")
        return
        
    with open(products_file, 'r') as f:
        products = json.load(f)

    # Initialize Gemini client
    client = genai.Client()
    
    # Ensure image directory exists
    os.makedirs('data/images', exist_ok=True)
    
    print(f"Generating images for {len(products)} products using Gemini 3.1 Flash...")
    
    for product in products:
        product_id = product['id']
        name = product['name']
        brand = product['brand']
        category = product['category']
        
        image_path = f"data/images/{product_id}.png"
        
        # Skip if already exists to save time/credits
        if os.path.exists(image_path):
            print(f"Skipping {product_id} - Image already exists")
            continue
            
        # Create prompt for standard packshot
        prompt = f"Studio lighting, flat lay, white background, {category} apparel item: {name} by {brand}. High quality catalog image."
        print(f"\nGenerating image for: [{category}] {name}")
        print(f"Prompt: {prompt}")
        
        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = client.models.generate_content(
                    model='gemini-3.1-flash-image-preview',
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                    )
                )
                
                if result.candidates and result.candidates[0].content.parts:
                    part = result.candidates[0].content.parts[0]
                    if part.inline_data:
                        with open(image_path, "wb") as f:
                            f.write(part.inline_data.data)
                        print(f"Saved to {image_path}")
                    else:
                        print(f"No inline_data found for {product_id}")
                else:
                    print(f"No image generated for {product_id}")
                break # Success, so break the retry loop
                    
            except Exception as e:
                print(f"Error generating image for {product_id} (Attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    sleep_time = 2 ** attempt * 5
                    print(f"Waiting {sleep_time} seconds before retrying...")
                    time.sleep(sleep_time)
                else:
                    print("Max retries reached. Moving to next product.")

if __name__ == "__main__":
    generate_product_images()
