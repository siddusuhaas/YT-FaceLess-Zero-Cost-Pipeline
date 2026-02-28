"""
scripts/list_voices.py
======================
Lists all available ElevenLabs voices and their IDs.
Use this to find the ID for an Indian voice you added to your Voice Lab.

Usage:
  export ELEVENLABS_API_KEY="your_key"
  python scripts/list_voices.py
"""
import os
from elevenlabs.client import ElevenLabs

api_key = os.environ.get("ELEVENLABS_API_KEY")
if not api_key:
    print("❌ Error: ELEVENLABS_API_KEY environment variable not set.")
    exit(1)

client = ElevenLabs(api_key=api_key)
response = client.voices.get_all()

print(f"\n🎙️  Available Voices ({len(response.voices)}):")
print("-" * 50)
print(f"{'NAME':<20} | {'VOICE ID'}")
print("-" * 50)
for v in response.voices:
    print(f"{v.name:<20} | {v.voice_id}")
print("-" * 50)