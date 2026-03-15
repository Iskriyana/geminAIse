from google.adk.agents import Agent
from google import genai
from google.genai import types
import os
import uuid
import json

# Store the latest user images per session
latest_user_images = {}

def find_product_image(product_name: str) -> bytes:
    """Attempt to find the pre-generated product image based on the product name."""
    try:
        products_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "products.json")
        if not os.path.exists(products_path):
            return None
            
        with open(products_path, "r") as f:
            products = json.load(f)
            
        # Very simple fuzzy match - check if any word in the product name matches
        best_match = None
        for p in products:
            if product_name.lower() in p["name"].lower() or p["name"].lower() in product_name.lower():
                best_match = p
                break
                
        if not best_match:
            # Fallback: just check for brand or category
            for p in products:
                if p["brand"].lower() in product_name.lower() or p["category"].lower() in product_name.lower():
                    best_match = p
                    break
                    
        if best_match:
            image_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "images", f"{best_match['id']}.png")
            if os.path.exists(image_path):
                with open(image_path, "rb") as f:
                    return f.read()
    except Exception as e:
        print(f"Error finding product image: {e}")
        
    return None

async def try_on_apparel(product_name: str, setting: str = "studio lighting") -> str:
    """
    Use this tool when the user asks to try on a specific apparel item, piece of clothing, or outfit.
    
    Args:
        product_name: The name or description of the apparel product the user wants to try on (e.g., "LnA Women's Alexandrine Sweater"). 
                      If the user asks to try on what you are seeing, describe it.
        setting: The background setting the user wants to be in (e.g. "at the beach", "in a cafe", "studio lighting"). Defaults to studio lighting.
    """
    # Find the latest user image (we'll just use the most recent one uploaded globally for this hackathon)
    if not latest_user_images:
        return "I'm sorry, but I don't have a photo of you yet. Please upload a photo first."
    
    # Get the last uploaded image
    session_id, user_image_bytes = list(latest_user_images.items())[-1]
    
    try:
        client = genai.Client()
        
        prompt = f"Seamlessly dress the person in the provided image with the {product_name}, placing them in a realistic {setting}."
        
        contents = [
            types.Part.from_bytes(data=user_image_bytes, mime_type="image/jpeg")
        ]
        
        product_image_bytes = find_product_image(product_name)
        if product_image_bytes:
            contents.append(types.Part.from_bytes(data=product_image_bytes, mime_type="image/png"))
            prompt += " Use the second image as the reference for the clothing item."
            
        contents.append(prompt)
        
        result = await client.aio.models.generate_content(
            model='gemini-3.1-flash-image-preview',
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            )
        )
        
        if result.candidates and result.candidates[0].content.parts:
            part = result.candidates[0].content.parts[0]
            if part.inline_data:
                filename = f"{uuid.uuid4()}.jpg"
                filepath = os.path.join(os.path.dirname(__file__), "..", "static", "tryon_images", filename)
                
                with open(filepath, "wb") as f:
                    f.write(part.inline_data.data)
                    
                # Return a simple string with the URL
                return f"I have generated the image of you wearing the {product_name} {setting}. The image URL is /static/tryon_images/{filename}. Tell the user the image is ready and repeat the exact URL in your response."
                
        return "I tried to generate the image, but something went wrong with the image generation service."
        
    except Exception as e:
        print(f"Error generating try-on image: {e}")
        return f"I encountered an error while trying to generate the image: {str(e)}"

root_agent = Agent(
    name="geminAIse",
    model="gemini-2.5-flash-native-audio-preview-12-2025",
    description="A Live API Virtual Try-On Assistant that acts as a personal shopper and stylist.",
    instruction=(
        "You are geminAIse, a helpful, enthusiastic, and friendly personal shopper and virtual stylist. "
        "You help users pick out outfits, provide fashion advice, and most importantly, allow them to virtually try on clothes. "
        "You have access to a live video stream from the user's camera (or their uploaded photos). "
        "When a user asks to see how they would look in an outfit, or asks to 'try something on', you MUST use the try_on_apparel tool. "
        "Keep your responses concise and conversational. "
        "CRITICAL INSTRUCTION: You communicate via voice. You MUST NOT output any internal thoughts, monologues, or actions. "
        "NEVER use asterisks (*) or markdown formatting. Speak directly and naturally to the user."
    ),
    tools=[try_on_apparel]
)
