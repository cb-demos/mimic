import asyncio
import os

from .creation_pipeline import CreationPipeline
from .scenarios import initialize_scenarios


async def main():
    print("CloudBees Creation Pipeline Demo")
    print("=" * 50)

    # Initialize scenarios
    scenario_manager = initialize_scenarios("scenarios")

    # Load the hackers-app scenario
    scenario = scenario_manager.get_scenario("hackers-app")
    if not scenario:
        print("❌ Scenario 'hackers-app' not found")
        return

    print(f"📋 Loaded scenario: {scenario.name}")
    print(f"📝 Description: {scenario.description}")
    print(f"📦 Repositories: {len(scenario.repositories)}")
    print(f"📱 Applications: {len(scenario.applications)}")
    print(f"🌍 Environments: {len(scenario.environments)}")
    print(f"🚩 Flags: {len(scenario.flags)}")

    # Define parameters
    parameters = {"project_name": "demo-hackers3", "target_org": "ldorg"}

    print(f"\n🎯 Parameters: {parameters}")
    print("=" * 50)

    # Create and execute pipeline
    unify_pat = os.getenv("UNIFY_API_KEY")
    if not unify_pat:
        print("❌ UNIFY_API_KEY environment variable is required")
        return

    pipeline = CreationPipeline(
        organization_id="a2742702-d1f3-4f3c-a309-30220c1a0504",
        endpoint_id="9a3942be-0e86-415e-94c5-52512be1138d",
        unify_pat=unify_pat,
        invitee_username="ldonleycb",
    )

    try:
        summary = await pipeline.execute_scenario(scenario, parameters)
        print("\n🎉 Pipeline completed successfully!")
        print(f"📊 Summary: {summary}")

    except Exception as e:
        print(f"❌ Pipeline failed: {e}")
        print("\nMake sure GITHUB_TOKEN and UNIFY_API_KEY are set in .env")
        raise


if __name__ == "__main__":
    asyncio.run(main())
