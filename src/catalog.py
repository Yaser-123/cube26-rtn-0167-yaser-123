# Seller catalogue used for the identity check. Synthetic, matching the SKUs in data/returns_sample.csv.
# In production this would come from the seller's listing data (title, images, identifying features).
CATALOG = {
    "SKU-BOTTLE-750": "750 ml insulated stainless-steel water bottle with screw-on lid",
    "SKU-CABLE-USBC": "USB-C charging cable",
    "SKU-CANDLE-3": "Set of 3 scented jar candles in a gift box",
    "SKU-LAMP-LED": "LED desk lamp with USB power cable and printed manual",
    "SKU-LEASH-6FT": "6 ft dog leash",
    "SKU-MUG-11": "Set of 2 ceramic 11 oz mugs",
    "SKU-PROT-1KG": "1 kg tub of protein powder with measuring scoop",
    "SKU-PUZZLE-500": "500-piece jigsaw puzzle with reference poster",
    "SKU-SERUM-30": "30 ml skincare serum in a glass dropper bottle with leaflet",
    "SKU-TOWEL-BLU": "Blue cotton bath towel",
}

# Expected parts per SKU, from data/returns_sample.csv
PARTS = {
    "SKU-BOTTLE-750": "bottle;lid",
    "SKU-CABLE-USBC": "cable",
    "SKU-CANDLE-3": "candle x3;gift box",
    "SKU-LAMP-LED": "lamp;usb cable;manual",
    "SKU-LEASH-6FT": "leash",
    "SKU-MUG-11": "mug x2",
    "SKU-PROT-1KG": "tub;scoop",
    "SKU-PUZZLE-500": "puzzle pieces;poster",
    "SKU-SERUM-30": "bottle;dropper;leaflet",
    "SKU-TOWEL-BLU": "towel",
}
