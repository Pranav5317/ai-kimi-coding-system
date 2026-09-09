---
name: unit-testing
description: Comprehensive unit test generation, test runners, assertions, and mock implementations.
target_agent: agent2
---

# Unit Testing & Verification Skill

When writing unit or integration tests for application modules:

## Key Guidelines
1. **Test Isolation**:
   - Use mock providers or temporary directories (`tempfile.mkdtemp()`) to keep test environments isolated.
2. **Coverage**:
   - Test both success paths and failure edge-cases (invalid inputs, missing resources, timeouts).
3. **Execution**:
   - Use standard test runners (`unittest`, `pytest`, `jest`).

