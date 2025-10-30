#!/usr/bin/env python3
"""
Interactive tool to map OCR names to clean display names.
Shows you all unmapped OCR names from your snapshots and lets you map them.
"""
import sys
import json
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from trading_app.utils import load_item_name_mapping, load_all_snapshots


def show_unmapped_items():
    """Show all items that don't have a display name mapping yet."""
    mapping = load_item_name_mapping()
    snapshots_path = Path(__file__).parent.parent / 'snapshots'
    snapshots = load_all_snapshots(str(snapshots_path))
    
    # Collect all unique OCR names with their prices
    ocr_names = {}
    for snap in snapshots:
        categories = snap.get('categories', {})
        for category, items in categories.items():
            for item in items:
                ocr_name = item.get('itemName', '')
                price = item.get('price', 0)
                if ocr_name and ocr_name not in mapping:
                    if ocr_name not in ocr_names:
                        ocr_names[ocr_name] = {'price': price, 'category': category}
    
    # Sort by category then price
    items_by_category = defaultdict(list)
    for ocr_name, info in ocr_names.items():
        items_by_category[info['category']].append((ocr_name, info['price']))
    
    # Sort within each category by price
    for category in items_by_category:
        items_by_category[category].sort(key=lambda x: x[1])
    
    return items_by_category


def add_mapping(ocr_name, display_name):
    """Add a new mapping to item_names.json."""
    mapping_file = Path(__file__).parent.parent / 'item_names.json'
    
    # Load existing mappings
    if mapping_file.exists():
        with open(mapping_file, 'r', encoding='utf-8') as f:
            mapping = json.load(f)
    else:
        mapping = {
            "_comment": "Map OCR names to clean display names. OCR names are unique identifiers."
        }
    
    # Add new mapping
    mapping[ocr_name] = display_name
    
    # Save back
    with open(mapping_file, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)
    
    print(f"[OK] Mapped: '{ocr_name}' -> '{display_name}'")


def find_similar_mapped_items(ocr_name, mapping):
    """Find items in mapping that are similar to the OCR name (might be variants)."""
    similar = []
    ocr_lower = ocr_name.lower()
    for mapped_ocr, display in mapping.items():
        if mapped_ocr.startswith('_'):  # Skip comments
            continue
        mapped_lower = mapped_ocr.lower()
        # Check if they share significant text
        if (ocr_lower[:5] in mapped_lower or mapped_lower[:5] in ocr_lower) and len(ocr_lower) > 5:
            similar.append((mapped_ocr, display))
    return similar


def interactive_mapping():
    """Interactive session to map all unmapped items."""
    print("\n" + "="*60)
    print("INTERACTIVE ITEM MAPPING")
    print("="*60)
    print("\nThis tool helps you map garbled OCR names to clean display names.")
    print("You only need to map each unique OCR name once.")
    print("\nCommands:")
    print("  <name>  - Enter a clean display name for this item")
    print("  s       - Skip this item (map later)")
    print("  q       - Quit")
    print("="*60 + "\n")
    
    items_by_category = show_unmapped_items()
    mapping = load_item_name_mapping()
    
    if not items_by_category:
        print("[OK] All items are already mapped!")
        return
    
    total_unmapped = sum(len(items) for items in items_by_category.values())
    print(f"Found {total_unmapped} unmapped items\n")
    
    mapped_count = 0
    
    for category, items in items_by_category.items():
        print(f"\n{'='*60}")
        print(f"Category: {category}")
        print('='*60)
        
        for ocr_name, price in items:
            print(f"\nOCR Name: '{ocr_name}'")
            print(f"Price: ${price:,}")
            
            # Show similar already-mapped items (might be variants)
            similar = find_similar_mapped_items(ocr_name, mapping)
            if similar:
                print(f"\nSimilar mapped items (might be the same item):")
                for sim_ocr, sim_display in similar[:3]:
                    print(f"  '{sim_ocr}' -> '{sim_display}'")
            
            response = input("\nEnter display name (or 's' to skip, 'q' to quit): ").strip()
            
            if response.lower() == 'q':
                print(f"\n[OK] Mapped {mapped_count} items. Run this tool again to continue.")
                return
            elif response.lower() == 's':
                print("[!] Skipped")
                continue
            elif response:
                add_mapping(ocr_name, response)
                mapping[ocr_name] = response  # Update local cache
                mapped_count += 1
            else:
                print("[!] Skipped (empty input)")
    
    print(f"\n[OK] All done! Mapped {mapped_count} items.")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Map OCR names to clean display names')
    parser.add_argument('--list', action='store_true', help='Just list unmapped items')
    parser.add_argument('--add', nargs=2, metavar=('OCR_NAME', 'DISPLAY_NAME'), 
                       help='Add a single mapping')
    
    args = parser.parse_args()
    
    if args.list:
        items_by_category = show_unmapped_items()
        if not items_by_category:
            print("[OK] All items are already mapped!")
            return
        
        total = sum(len(items) for items in items_by_category.values())
        print(f"\nUnmapped items: {total}\n")
        for category, items in items_by_category.items():
            print(f"\n{category}:")
            for ocr_name, price in items:
                print(f"  ${price:>8,} - {ocr_name}")
    
    elif args.add:
        add_mapping(args.add[0], args.add[1])
    
    else:
        interactive_mapping()


if __name__ == '__main__':
    main()

