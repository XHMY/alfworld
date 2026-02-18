#!/usr/bin/env python
"""
Example: Running parallel ALFWorld text environments in Docker

This script demonstrates how to run multiple ALFWorld environments in parallel
using Docker containers. This is useful for:
- Training agents with parallel experience collection
- Evaluating agents across multiple environments simultaneously
- Scaling up experimentation

Usage:
    # Inside Docker container:
    python examples/parallel_envs_example.py

    # Or from host with docker-compose:
    docker-compose run alfworld-env-1 python examples/parallel_envs_example.py

Note on Multiprocessing:
    This example uses multiprocessing.Pool. If you encounter pickling/serialization
    errors with complex game state objects, particularly on Windows or macOS, try
    setting the multiprocessing start method to 'spawn':
    
        import multiprocessing as mp
        if __name__ == "__main__":
            mp.set_start_method('spawn', force=True)
"""

import numpy as np
import multiprocessing as mp
from alfworld.agents.environment import get_environment
import alfworld.agents.modules.generic as generic


def run_environment(worker_id, num_episodes=5):
    """Run a single environment for multiple episodes.
    
    Args:
        worker_id: Numeric identifier for this worker process
        num_episodes: Number of episodes to run
    """
    print(f"[Worker {worker_id}] Starting environment...")
    
    # Load config
    config = generic.load_config()
    config['env']['type'] = 'AlfredTWEnv'  # Text-only environment
    
    # Setup environment with batch_size=1 for single environment
    env = get_environment(config['env']['type'])(config, train_eval='train')
    env = env.init_env(batch_size=1)
    
    results = []
    
    for episode in range(num_episodes):
        print(f"[Worker {worker_id}] Episode {episode + 1}/{num_episodes}")
        
        # Reset environment
        obs, info = env.reset()
        
        total_steps = 0
        total_reward = 0
        done = False
        
        while not done and total_steps < 50:  # Max 50 steps per episode
            # Get random action from admissible commands
            admissible_commands = list(info['admissible_commands'])
            if len(admissible_commands[0]) > 0:
                action = [np.random.choice(admissible_commands[0])]
            else:
                action = ["look"]  # Default action if no admissible commands
            
            # Step environment
            obs, scores, dones, infos = env.step(action)
            
            total_steps += 1
            total_reward = scores[0]
            done = dones[0]
            info = infos
        
        result = {
            'worker_id': worker_id,
            'episode': episode,
            'steps': total_steps,
            'reward': total_reward,
            'success': done and total_reward > 0
        }
        results.append(result)
        print(f"[Worker {worker_id}] Episode {episode + 1} completed: {result}")
    
    return results


def run_parallel_environments(num_envs=4, episodes_per_env=5):
    """Run multiple environments in parallel using multiprocessing."""
    print(f"Starting {num_envs} parallel environments...")
    print(f"Each environment will run {episodes_per_env} episodes")
    print("-" * 60)
    
    # Create a pool of workers
    with mp.Pool(processes=num_envs) as pool:
        # Run environments in parallel
        all_results = pool.starmap(
            run_environment,
            [(i, episodes_per_env) for i in range(num_envs)]
        )
    
    # Flatten results
    results = [r for env_results in all_results for r in env_results]
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    total_episodes = len(results)
    total_steps = sum(r['steps'] for r in results)
    total_success = sum(1 for r in results if r['success'])
    
    print(f"Total Episodes: {total_episodes}")
    print(f"Total Steps: {total_steps}")
    print(f"Success Rate: {total_success}/{total_episodes} ({100*total_success/total_episodes:.1f}%)")
    print(f"Average Steps per Episode: {total_steps/total_episodes:.1f}")
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Run parallel ALFWorld text environments"
    )
    parser.add_argument(
        "--num-envs",
        type=int,
        default=4,
        help="Number of parallel environments (default: 4)"
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=5,
        help="Number of episodes per environment (default: 5)"
    )
    
    args = parser.parse_args()
    
    results = run_parallel_environments(
        num_envs=args.num_envs,
        episodes_per_env=args.episodes
    )
