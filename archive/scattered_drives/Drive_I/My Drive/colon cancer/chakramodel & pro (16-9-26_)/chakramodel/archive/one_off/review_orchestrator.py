import asyncio
import json
import os
import sys
from google.antigravity import Agent, LocalAgentConfig, types

PAPER_FILE = "ChakraModel_Final_Paper.md"
STATE_FILE = "review_state.json"
MAX_CYCLES = 36

DISCRIMINATOR_PROMPT = """You are a highly critical MICCAI/IEEE TMI reviewer.
Your objective is to find genuine methodological flaws, statistical errors, unverified claims, or missing experiments in the CURRENT draft of the ChakraModel paper.
You MUST verify claims against actual code, logs, and outputs in the repository.
If you find claims that are not backed up by real, reproducible results, flag them immediately.
Rely on skills like bmad-review-adversarial-general and bmad-review-edge-case-hunter.
"""

GENERATOR_PROMPT = """You are a rigorously honest researcher and developer.
Your objective is to execute required tests, reproduce numbers, and pull logs to address the flaws identified by the Discriminators.
You have ONLY the following allowed actions:
(a) Run the actual missing experiment/ablation and report the REAL result. Do NOT adjust wording to obscure a weak real result.
(b) If a claimed number cannot be reproduced from actual code/logs, replace it in the text with the verified real number, even if it is lower.
(c) If a component (e.g., ChakraSLAM) was not actually implemented or tested, explicitly mark it as "proposed / future work"—never as "evaluated."

HARD RULE: No text-only rewrites are allowed to soften, obscure, or rephrase a methodological weakness without an underlying code/experiment change.
Use skills like bmad-dev-auto, bmad-testarch-automate, and bmad-testarch-nfr.
Modify the paper directly if needed.
"""

async def run_review_loop():
    print("Initializing Google Antigravity SDK multi-agent review loop...")
    
    # Define 6 Discriminator subagents
    discriminators = []
    for i in range(6):
        discriminators.append(
            types.SubagentConfig(
                name=f"discriminator_{i}",
                description="Highly critical MICCAI/IEEE TMI reviewer looking for flaws.",
                capabilities=types.SubagentCapabilities(
                    agent_behavior=types.AgentBehavior.AUTONOMOUS,
                    enabled_tools=[types.BuiltinTools.RUN_COMMAND, types.BuiltinTools.VIEW_FILE, types.BuiltinTools.GREP_SEARCH, types.BuiltinTools.LIST_DIR],
                ),
                system_instruction=DISCRIMINATOR_PROMPT
            )
        )
    
    # Define the Generator subagent
    generator = types.SubagentConfig(
        name="generator",
        description="Researcher executing tests and rigorously updating the paper with real numbers.",
        capabilities=types.SubagentCapabilities(
            agent_behavior=types.AgentBehavior.AUTONOMOUS,
            enabled_tools=[types.BuiltinTools.RUN_COMMAND, types.BuiltinTools.VIEW_FILE, types.BuiltinTools.WRITE_TO_FILE, types.BuiltinTools.REPLACE_FILE_CONTENT, types.BuiltinTools.MULTI_REPLACE_FILE_CONTENT, types.BuiltinTools.GREP_SEARCH, types.BuiltinTools.LIST_DIR],
        ),
        system_instruction=GENERATOR_PROMPT
    )

    config = LocalAgentConfig(
        subagents=discriminators + [generator],
        capabilities=types.CapabilitiesConfig(
            enable_subagents=True,
            max_subagent_depth=2,
            allowed_subagents=[f"discriminator_{i}" for i in range(6)] + ["generator"]
        )
    )

    # State tracking
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
    else:
        state = {"cycles_completed": 0, "history": []}

    async with Agent(config) as agent:
        start_cycle = state["cycles_completed"]
        
        for cycle in range(start_cycle, MAX_CYCLES):
            print(f"\n{'='*50}\n--- Starting Cycle {cycle + 1} of {MAX_CYCLES} ---\n{'='*50}")
            
            # Step 1: Run Discriminators
            print("\n[Phase 1] Spawning 6 Discriminator subagents to audit the paper...")
            disc_prompt = (
                f"Please instruct your 6 discriminator subagents (discriminator_0 through discriminator_5) "
                f"to rigorously review {PAPER_FILE} against the current project logs/code. "
                f"They should act like a bmad-party-mode roundtable, but focus solely on finding flaws. "
                f"Compile their findings into a concise list of methodological weaknesses, unverified claims, or missing experiments."
            )
            response = await agent.chat(disc_prompt)
            flaws = await response.text()
            print("\n--- Discriminator Findings ---")
            print(flaws)
            print("------------------------------")
            
            # Step 2: Run Generator
            print("\n[Phase 2] Spawning Generator subagent to run experiments and fix the paper...")
            gen_prompt = (
                f"Please instruct the 'generator' subagent to address the following flaws identified by the discriminators:\n\n{flaws}\n\n"
                f"The generator MUST strictly adhere to the rules: run actual experiments/scripts to verify numbers. "
                f"If a number is unverified, replace it with the real one. If un-implemented, label as 'proposed/future work'. "
                f"Do not just soften the wording. Apply any necessary changes to {PAPER_FILE} and report the diff."
            )
            response = await agent.chat(gen_prompt)
            fixes = await response.text()
            print("\n--- Generator Actions & Diffs ---")
            print(fixes)
            print("---------------------------------")
            
            # Step 3: Human-in-the-Loop Checkpoint
            print("\n[Phase 3] Checkpoint Preview - Human in the Loop")
            print("Please review the diffs and generator actions above.")
            
            # Wait for human sign-off
            user_input = input("Do you approve these changes to continue to the next cycle? (yes/no): ")
            
            if user_input.lower().strip() not in ['yes', 'y']:
                print("\n[!] Execution halted by user. Changes not approved or loop aborted.")
                sys.exit(0)
                
            print(f"\n[✓] Cycle {cycle + 1} approved by user.")
            
            # Update state
            state["cycles_completed"] = cycle + 1
            state["history"].append({
                "cycle": cycle + 1,
                "discriminator_findings": flaws,
                "generator_actions": fixes
            })
            
            with open(STATE_FILE, "w") as f:
                json.dump(state, f, indent=2)

if __name__ == "__main__":
    try:
        asyncio.run(run_review_loop())
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
