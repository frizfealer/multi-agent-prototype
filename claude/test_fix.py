#!/usr/bin/env python3
"""
Quick test script to verify the requirement context fix
"""
import asyncio
from client import DynamicExercisePlanningClient

async def test_requirement_context_fix():
    """Test that final plans correctly show which requirement they address"""
    print("🧪 Testing Requirement Context Fix")
    print("=" * 50)
    
    client = DynamicExercisePlanningClient()
    
    # Shorter, focused test with clear progression
    initial_message = "6-week plan to get wider, 3x weekly"
    updates = [
        "Change to 2x weekly only", 
        "Dumbbells only, no gym",
        "Focus on shoulders, not back"
    ]
    update_delays = [8, 10, 8]  # Shorter delays for faster testing
    
    print(f"🚀 Running focused test:")
    print(f"  Requirement #1: {initial_message}")
    print(f"  Requirement #2: {updates[0]}")
    print(f"  Requirement #3: {updates[1]}")
    print(f"  Requirement #4: {updates[2]}")
    print()
    print("Expected fixes:")
    print("  ✅ Correct requirement numbers (1, 2, 3, 4)")
    print("  ✅ Correct 'Updated from' showing previous requirement, not original")
    print()
    
    await client.run_with_updates(initial_message, updates, update_delays)
    
    print("\n✅ Test completed! Check the output above to verify:")
    print("  1. Each final plan shows correct requirement number")
    print("  2. Each final plan shows correct requirement text") 
    print("  3. Final summary shows plan-to-requirement mapping")

if __name__ == "__main__":
    asyncio.run(test_requirement_context_fix())