# My-Commit - Minimal Git Commit Skills

## Overview

A minimal Git commit skills package for the AI Knowledge Base Assistant project. This skill provides automated commit workflows, commit message generation, and best practice guidance.

## Features

### 1. Automated Commit Workflow
- Automatic detection of untracked and modified files
- Intelligent commit grouping (by feature module, file type)
- Support for Conventional Commits specification

### 2. Commit Message Generation
- Automatic generation of standardized commit messages
- Support for English commit messages
- Appropriate commit types and scopes

### 3. Best Practice Validation
- Check commit atomicity
- Validate commit message format
- Ensure code quality

## Usage Scenarios

### Scenario 1: New Feature Commit
When adding new features:
```bash
# Skill automatically detects new files
# Generates commit message like "feat: add GitHub trending collection"
```

### Scenario 2: Documentation Update Commit
When updating documentation:
```bash
# Skill identifies documentation files
# Generates commit message like "docs: update AGENTS.md with实践经验"
```

### Scenario 3: Bug Fix Commit
When fixing bugs:
```bash
# Skill detects fixed files
# Generates commit message like "fix: resolve data collection issue"
```

## Skill Configuration

### File Structure
```
.opencode/skills/my-commit/
├── SKILL.md              # Skill documentation (this file)
├── commit-templates/     # Commit template directory
│   ├── feat.md          # Feature addition template
│   ├── fix.md           # Bug fix template
│   ├── docs.md          # Documentation update template
│   └── chore.md         # Chore task template
└── scripts/             # Helper scripts
    └── validate-commit.sh # Commit validation script
```

### Commit Type Mapping
| Type | Emoji | Description | Use Case |
|------|-------|-------------|----------|
| `feat` | ✨ | New feature | Adding new features, modules |
| `fix` | 🐛 | Bug fix | Fixing code defects |
| `docs` | 📝 | Documentation | Updating documentation, comments |
| `style` | 🎨 | Code style | Formatting, code style adjustments |
| `refactor` | ♻️ | Code refactor | Refactoring code without changing functionality |
| `test` | ✅ | Test related | Adding or modifying tests |
| `chore` | 🔧 | Chore tasks | Build configuration, tool updates |

## Usage Guide

### Basic Usage
1. **Detect Changes**: Skill automatically scans workspace changes
2. **Intelligent Grouping**: Group commits by file type and feature module
3. **Generate Messages**: Generate appropriate commit messages based on change type
4. **Execute Commit**: Execute git add and git commit

### Advanced Features
1. **Batch Commits**: Support for batch commits of related changes
2. **Commit Validation**: Validate commit message format
3. **History Analysis**: Analyze commit history and provide improvement suggestions

## Integration

### Agent Integration
Integrate this skill into Collector, Analyzer, or Distributor Agents:

```yaml
# Add to Agent configuration
skills:
  - my-commit
```

### Manual Trigger
Can also be triggered manually via command line:
```bash
# Use skill for commits
npx @opencode-ai/plugin my-commit
```

## Best Practices

### Commit Standards
1. **Atomic Commits**: Each commit does one thing
2. **Clear Description**: Commit messages should be clear and concise
3. **Correct Type**: Choose appropriate commit type
4. **Clear Scope**: Specify scope when necessary

### Code Quality
1. **Tests Pass**: Ensure tests pass before committing
2. **Code Review**: Important commits should be code reviewed
3. **Documentation Updated**: Update relevant documentation with code changes

## Examples

### Example 1: New Collection Feature
```bash
# Detects new collection-related files
# Generated commit message:
feat(collector): add GitHub trending data collection

- implement websearch-based data collection
- add data validation and formatting
- update AGENTS.md with practical experience
```

### Example 2: Update Project Documentation
```bash
# Detects updates to AGENTS.md file
# Generated commit message:
docs: update AGENTS.md with practical experience section

- add tool selection experience summary
- document problem-solving patterns
- update version to 1.1.0
```

### Example 3: Fix Data Format Issue
```bash
# Detects JSON data format fixes
# Generated commit message:
fix(data): correct JSON formatting in trending data

- fix missing fields in JSON structure
- improve data validation logic
- update collection timestamp format
```

## Troubleshooting

### Common Issues
1. **Commit Failure**: Check git configuration and permissions
2. **Invalid Message**: Check commit message format
3. **Untracked Files**: Ensure files are added to git

### Debug Mode
Enable debug mode for detailed logs:
```bash
DEBUG=my-commit npx @opencode-ai/plugin my-commit
```

## Changelog

### v1.0.0 (2026-04-21)
- Initial release
- Basic commit functionality
- Commit templates and validation

## Contributing

Welcome contributions and improvements:
1. Fork the project repository
2. Create a feature branch
3. Commit your changes
4. Create a Pull Request

## License

MIT License