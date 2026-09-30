import json
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def run_test():
    # Construct a sample payload matching the ReturnCaptureRequest schema
    payload = {
        "unit_id": "UNIT-0018",
        "organization_id": "org_demo_bravo",
        "operator_label": "op_fatima",
        "order_id": "ORD-DUMMY-50018",
        "ordered_sku": "SKU-BOTTLE-750",
        "parts_list": "bottle;lid",
        "photo_refs": ["fixtures/returns/UNIT-0018_1.jpg", "fixtures/returns/UNIT-0018_2.jpg"]
    }

    print("Sending request to /api/v1/returns/process...")
    
    # Make the request. Notice the required header x-org-id for tenancy isolation
    response = client.post(
        "/api/v1/returns/process",
        json=payload,
        headers={"x-org-id": "org_demo_bravo"}
    )
    
    print(f"Status Code: {response.status_code}")
    print("Response JSON:")
    print(json.dumps(response.json(), indent=2))

if __name__ == "__main__":
    run_test()
