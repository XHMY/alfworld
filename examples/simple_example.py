#!/usr/bin/env python
"""
Simple example: Running a single ALFWorld text environment

This is a basic example showing how to use ALFWorld text environment
in a Docker container.

Usage:
    python examples/simple_example.py
"""

import numpy as np
from alfworld.agents.environment import get_environment
import alfworld.agents.modules.generic as generic


def main():
    print("Loading ALFWorld text environment...")
    
    # Load config
    config = generic.load_config()
    config['env']['type'] = 'AlfredTWEnv'  # Text-only environment
    
    # Setup environment
    env = get_environment(config['env']['type'])(config, train_eval='train')
    env = env.init_env(batch_size=1)
    
    print("\nEnvironment loaded successfully!")
    print("Running a random agent for 1 episode...\n")
    
    # Reset environment
    obs, info = env.reset()
    print(f"Initial observation:\n{obs[0]}\n")
    
    total_steps = 0
    max_steps = 50
    
    while total_steps < max_steps:
        # Get random action from admissible commands
        admissible_commands = list(info['admissible_commands'])
        
        if len(admissible_commands[0]) > 0:
            action = [np.random.choice(admissible_commands[0])]
        else:
            action = ["look"]
        
        print(f"Step {total_steps + 1}: {action[0]}")
        
        # Step environment
        obs, scores, dones, infos = env.step(action)
        
        print(f"  Observation: {obs[0][:100]}...")  # Print first 100 chars
        print(f"  Score: {scores[0]}")
        
        total_steps += 1
        
        if dones[0]:
            if scores[0] > 0:
                print(f"\n✓ Task completed successfully in {total_steps} steps!")
            else:
                print(f"\n✗ Task failed after {total_steps} steps")
            break
        
        info = infos
    
    if not dones[0]:
        print(f"\n⊗ Episode terminated after {max_steps} steps (max limit)")
    
    print("\nExample completed!")


if __name__ == "__main__":
    main()
