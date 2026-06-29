import sys
import os

# Ensure we can import from our local modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.planner import run_query

print('='*60)
print('TEST 1: Architecture Query')
print('='*60)
result = run_query('Show me the architecture and structure of this codebase')
print(result)

print('\n' + '='*60)
print('TEST 2: Impact Analysis Query')
print('='*60)
result = run_query('What breaks if I change `request`?')
print(result)

print('\n' + '='*60)
print('TEST 3: Dead Code Detection')
print('='*60)
result = run_query('Find all dead and unused functions')
print(result)

print('\n' + '='*60)
print('TEST 4: Edge Case - Unknown function')
print('='*60)
result = run_query('What is the impact if I change `nonexistent_function_xyz`?')
print(result)

print('\n' + '='*60)
print('TEST 5: Edge Case - Vague query (no function name)')
print('='*60)
result = run_query('What will break if I make changes?')
print(result)
