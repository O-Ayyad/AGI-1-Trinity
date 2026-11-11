import os 

DEFAULT_MODEL = os.environ.get(
    "CLAUDE_MODEL",
    "your_claude_model"
)


def generate_plan(system_prompt, user_prompt):
    #TODO: 
    # Currently uses a mock response
    #  Replace with Claude API Integration

    return {
        "tasks": [
        {
            "id": 1,
            "description": "Implement functionality",
            "assigned_to": "coder",
            "depends_on": []
        },
        {
            "id": 2,
            "description": "Test application functionality",
            "assigned_to": "tester",
            "depends_on": [1]
        }

    ]
}    