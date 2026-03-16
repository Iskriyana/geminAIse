import os
import json
from google.cloud import bigquery

def extract_products():
    # Initialize BigQuery client
    # Assumes google application credentials are set locally
    client = bigquery.Client()
    
    # Query 5 tops and 5 bottoms
    query = """
    WITH tops AS (
        SELECT id, name, category, brand, retail_price 
        FROM `bigquery-public-data.thelook_ecommerce.products`
        WHERE category IN ('Tops & Tees', 'Sweaters', 'Blazers & Jackets', 'Outerwear & Coats') 
          AND department = 'Women'
        LIMIT 5
    ),
    bottoms AS (
        SELECT id, name, category, brand, retail_price 
        FROM `bigquery-public-data.thelook_ecommerce.products`
        WHERE category IN ('Pants', 'Jeans', 'Skirts', 'Shorts') 
          AND department = 'Women'
        LIMIT 5
    )
    SELECT * FROM tops
    UNION ALL
    SELECT * FROM bottoms
    """
    
    print("Querying BigQuery to extract 10 catalog items...")
    query_job = client.query(query)
    results = query_job.result()
    
    products = []
    for row in results:
        products.append({
            "id": row.id,
            "name": row.name,
            "category": row.category,
            "brand": row.brand,
            "retail_price": float(row.retail_price) if row.retail_price else None
        })
        
    # Ensure data directory exists
    os.makedirs('data', exist_ok=True)
    
    output_path = 'data/products.json'
    with open(output_path, 'w') as f:
        json.dump(products, f, indent=4)
        
    print(f"Successfully extracted {len(products)} products and saved to {output_path}")
    for p in products:
        print(f" - [{p['category']}] {p['name']} ({p['brand']})")

if __name__ == "__main__":
    extract_products()
