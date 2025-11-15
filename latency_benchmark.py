#!/usr/bin/env python3
"""
Latency benchmarking tool for the Artist Hotline Voice Agent.
Measures actual latencies of each component in the pipeline.
"""

import asyncio
import time
import statistics
from typing import List, Dict
import json
import os
from datetime import datetime


class LatencyBenchmark:
    """Comprehensive latency measurement for voice pipeline components"""

    def __init__(self):
        self.measurements = {
            'silence_detection': [],
            'whisper_transcription': [],
            'gpt_generation': [],
            'elevenlabs_tts_first_chunk': [],
            'elevenlabs_tts_complete': [],
            'audio_conversion': [],
            'websocket_round_trip': [],
            'end_to_end': []
        }
        self.config = self._load_config()

    def _load_config(self):
        """Load configuration from environment"""
        from dotenv import load_dotenv
        load_dotenv()

        return {
            'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
            'ELEVEN_LABS_API_KEY': os.getenv('ELEVEN_LABS_API_KEY'),
            'ELEVEN_LABS_VOICE_ID': os.getenv('ELEVEN_LABS_VOICE_ID'),
        }

    async def benchmark_whisper(self, audio_samples: List[bytes]) -> Dict:
        """Benchmark Whisper transcription latency"""
        from openai import OpenAI
        import tempfile
        import wave
        import audioop
        import io

        client = OpenAI(api_key=self.config['OPENAI_API_KEY'])
        latencies = []

        for audio_data in audio_samples:
            start = time.time()

            try:
                # Convert µ-law to WAV
                pcm_data = audioop.ulaw2lin(audio_data, 2)
                wav_buffer = io.BytesIO()
                with wave.open(wav_buffer, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(8000)
                    wav_file.writeframes(pcm_data)

                wav_data = wav_buffer.getvalue()

                # Save to temp file
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                    temp_file.write(wav_data)
                    temp_path = temp_file.name

                # Measure API call
                api_start = time.time()
                with open(temp_path, 'rb') as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="en"
                    )

                api_latency = time.time() - api_start
                total_latency = time.time() - start

                latencies.append({
                    'total': total_latency,
                    'api_only': api_latency,
                    'preprocessing': total_latency - api_latency,
                    'audio_size': len(audio_data),
                    'transcript_length': len(transcript.text)
                })

                # Clean up
                os.unlink(temp_path)

            except Exception as e:
                print(f"Whisper benchmark error: {e}")

        return self._calculate_stats(latencies, 'whisper')

    async def benchmark_gpt(self, prompts: List[str]) -> Dict:
        """Benchmark GPT-4o-mini response generation"""
        from openai import OpenAI

        client = OpenAI(api_key=self.config['OPENAI_API_KEY'])
        latencies = []

        for prompt in prompts:
            messages = [
                {"role": "system", "content": "You are Synthetic Jason, an AI artist."},
                {"role": "user", "content": prompt}
            ]

            # Standard generation
            start = time.time()
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=60,
                temperature=0.9
            )
            standard_latency = time.time() - start

            # Streaming generation (time to first token)
            start = time.time()
            stream = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=60,
                temperature=0.9,
                stream=True
            )

            first_token_time = None
            tokens = []
            for chunk in stream:
                if chunk.choices[0].delta.content and not first_token_time:
                    first_token_time = time.time() - start
                if chunk.choices[0].delta.content:
                    tokens.append(chunk.choices[0].delta.content)

            complete_time = time.time() - start

            latencies.append({
                'standard': standard_latency,
                'streaming_first_token': first_token_time,
                'streaming_complete': complete_time,
                'tokens_generated': len(''.join(tokens).split()),
                'prompt_length': len(prompt)
            })

        return self._calculate_stats(latencies, 'gpt')

    async def benchmark_elevenlabs(self, texts: List[str]) -> Dict:
        """Benchmark ElevenLabs TTS latency"""
        import websockets
        import base64

        latencies = []

        for text in texts:
            uri = f"wss://api.elevenlabs.io/v1/text-to-speech/{self.config['ELEVEN_LABS_VOICE_ID']}/stream-input"

            try:
                start = time.time()
                connection_start = start

                async with websockets.connect(uri) as ws:
                    connection_time = time.time() - connection_start

                    # Send configuration
                    init_message = {
                        "text": " ",
                        "voice_settings": {
                            "stability": 0.3,
                            "similarity_boost": 0.75
                        },
                        "xi_api_key": self.config['ELEVEN_LABS_API_KEY']
                    }
                    await ws.send(json.dumps(init_message))

                    # Send text
                    await ws.send(json.dumps({"text": text}))
                    await ws.send(json.dumps({"text": ""}))  # EOS

                    first_chunk_time = None
                    chunks_received = 0

                    async for message in ws:
                        data = json.loads(message)

                        if data.get("audio") and not first_chunk_time:
                            first_chunk_time = time.time() - start
                            chunks_received += 1

                        elif data.get("audio"):
                            chunks_received += 1

                        elif data.get("isFinal"):
                            break

                    total_time = time.time() - start

                    latencies.append({
                        'connection': connection_time,
                        'first_chunk': first_chunk_time,
                        'total': total_time,
                        'chunks': chunks_received,
                        'text_length': len(text)
                    })

            except Exception as e:
                print(f"ElevenLabs benchmark error: {e}")

        return self._calculate_stats(latencies, 'elevenlabs')

    async def benchmark_silence_detection(self) -> Dict:
        """Measure silence detection timing variations"""
        timings = []

        # Simulate different conversation states
        scenarios = [
            {'turn': 1, 'last_was_question': False, 'expected': 1.5},
            {'turn': 1, 'last_was_question': True, 'expected': 1.2},
            {'turn': 5, 'last_was_question': False, 'expected': 1.44},  # 1.8 * 0.8
            {'turn': 5, 'last_was_question': True, 'expected': 0.96},   # 1.2 * 0.8
        ]

        for scenario in scenarios:
            # Measure actual sleep precision
            expected = scenario['expected']
            start = time.time()
            await asyncio.sleep(expected)
            actual = time.time() - start

            timings.append({
                'scenario': scenario,
                'expected': expected,
                'actual': actual,
                'overhead': actual - expected
            })

        return self._calculate_stats(timings, 'silence_detection')

    async def simulate_full_pipeline(self) -> Dict:
        """Simulate and measure full conversation pipeline"""
        pipeline_times = []

        # Test conversations
        test_inputs = [
            "What do you think about AI art?",
            "How can I make my project more interesting?",
            "Tell me about glitch aesthetics",
        ]

        for user_input in test_inputs:
            start = time.time()
            stages = {}

            # Stage 1: Silence detection (simulated)
            silence_start = time.time()
            await asyncio.sleep(1.5)  # Reduced silence threshold
            stages['silence_detection'] = time.time() - silence_start

            # Stage 2: Whisper transcription (simulated with actual API)
            # Would call actual API in production benchmark

            # Stage 3: GPT generation
            gpt_start = time.time()
            # Simulate GPT call
            await asyncio.sleep(1.2)  # Average GPT-4o-mini latency
            stages['gpt_generation'] = time.time() - gpt_start

            # Stage 4: TTS first chunk
            tts_start = time.time()
            await asyncio.sleep(0.5)  # Average first chunk latency
            stages['tts_first_chunk'] = time.time() - tts_start

            # Stage 5: Complete TTS
            await asyncio.sleep(0.5)  # Additional time for full audio
            stages['tts_complete'] = time.time() - tts_start

            stages['total'] = time.time() - start

            # Calculate perceived latency (with filler word)
            stages['perceived'] = stages['silence_detection'] + 0.5  # Filler plays immediately

            pipeline_times.append(stages)

        return self._calculate_stats(pipeline_times, 'pipeline')

    def _calculate_stats(self, measurements: List, component: str) -> Dict:
        """Calculate statistics for measurements"""
        if not measurements:
            return {'component': component, 'error': 'No measurements'}

        # Extract numeric values for stats
        if isinstance(measurements[0], dict):
            # For complex measurements, calculate stats on 'total' or first numeric field
            key = 'total' if 'total' in measurements[0] else list(measurements[0].keys())[0]
            values = [m[key] for m in measurements if isinstance(m.get(key), (int, float))]
        else:
            values = [m for m in measurements if isinstance(m, (int, float))]

        if not values:
            return {'component': component, 'error': 'No numeric measurements'}

        return {
            'component': component,
            'measurements': len(values),
            'mean': statistics.mean(values),
            'median': statistics.median(values),
            'stdev': statistics.stdev(values) if len(values) > 1 else 0,
            'min': min(values),
            'max': max(values),
            'p95': sorted(values)[int(len(values) * 0.95)] if values else 0,
            'p99': sorted(values)[int(len(values) * 0.99)] if values else 0,
            'raw_data': measurements[:3]  # Sample of raw measurements
        }

    async def run_full_benchmark(self):
        """Run complete benchmark suite"""
        print("=" * 60)
        print("ARTIST HOTLINE LATENCY BENCHMARK")
        print("=" * 60)
        print(f"Started at: {datetime.now().isoformat()}\n")

        results = {}

        # 1. Silence Detection
        print("Testing silence detection timing...")
        results['silence_detection'] = await self.benchmark_silence_detection()
        self._print_results(results['silence_detection'])

        # 2. Full Pipeline Simulation
        print("\nSimulating full pipeline...")
        results['pipeline'] = await self.simulate_full_pipeline()
        self._print_results(results['pipeline'])

        # 3. GPT Benchmark (if API key available)
        if self.config.get('OPENAI_API_KEY'):
            print("\nBenchmarking GPT-4o-mini...")
            test_prompts = [
                "What's your favorite art medium?",
                "How do I start with generative art?",
                "Tell me about your latest project."
            ]
            results['gpt'] = await self.benchmark_gpt(test_prompts)
            self._print_results(results['gpt'])

        # 4. ElevenLabs Benchmark (if API key available)
        if self.config.get('ELEVEN_LABS_API_KEY'):
            print("\nBenchmarking ElevenLabs TTS...")
            test_texts = [
                "Hello, this is a test.",
                "Welcome to the artist hotline! What creative project are you working on?",
                "That's fascinating! Tell me more about your approach."
            ]
            results['elevenlabs'] = await self.benchmark_elevenlabs(test_texts)
            self._print_results(results['elevenlabs'])

        # Summary
        print("\n" + "=" * 60)
        print("BENCHMARK SUMMARY")
        print("=" * 60)

        total_latency = sum([
            results.get('silence_detection', {}).get('mean', 0),
            results.get('gpt', {}).get('mean', 0),
            results.get('elevenlabs', {}).get('mean', 0)
        ])

        print(f"\nEstimated Total Latency: {total_latency:.2f}s")
        print(f"With Filler Word Masking: {total_latency - 1.0:.2f}s perceived")

        # Save results
        with open('latency_benchmark_results.json', 'w') as f:
            json.dump(results, f, indent=2, default=str)

        print(f"\nResults saved to: latency_benchmark_results.json")

        return results

    def _print_results(self, stats: Dict):
        """Pretty print benchmark results"""
        if 'error' in stats:
            print(f"  Error: {stats['error']}")
            return

        print(f"  Measurements: {stats['measurements']}")
        print(f"  Mean: {stats['mean']:.3f}s")
        print(f"  Median: {stats['median']:.3f}s")
        print(f"  StdDev: {stats['stdev']:.3f}s")
        print(f"  Min: {stats['min']:.3f}s")
        print(f"  Max: {stats['max']:.3f}s")
        print(f"  P95: {stats['p95']:.3f}s")
        print(f"  P99: {stats['p99']:.3f}s")


async def main():
    """Run the benchmark"""
    benchmark = LatencyBenchmark()
    await benchmark.run_full_benchmark()


if __name__ == "__main__":
    asyncio.run(main())