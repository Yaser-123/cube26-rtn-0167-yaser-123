$headers = @{
    "Content-Type" = "application/json"
    "x-org-id" = "org_demo_bravo"
}

$body = @{
    "unit_id" = "UNIT-0018"
    "organization_id" = "org_demo_bravo"
    "operator_label" = "op_fatima"
    "order_id" = "ORD-DUMMY-50018"
    "ordered_sku" = "SKU-BOTTLE-750"
    "parts_list" = "bottle;lid"
    "photo_refs" = @(
        "fixtures/returns/UNIT-0018_1.jpg",
        "fixtures/returns/UNIT-0018_2.jpg"
    )
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/returns/process" -Method Post -Headers $headers -Body $body
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Host "Error: $_"
}
