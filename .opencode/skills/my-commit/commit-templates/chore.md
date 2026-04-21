# Chore Task Commit Template

## Template Description
For commits related to build configuration, tool updates, dependency management, or other maintenance tasks.

## Commit Format
```
chore: <brief description>

- <specific task 1>
- <specific task 2>
- <specific task 3>

<optional: related issue or PR>
```

## Field Description
- **brief description**: Under 50 words, describes the chore task
- **specific tasks**: Start with verbs, describe concrete task details

## Examples

### Example 1: Update Dependencies
```
chore: update project dependencies

- upgrade @opencode-ai/plugin to v1.4.6
- update Python requirements
- fix security vulnerabilities

Related to #12
```

### Example 2: Configuration Update
```
chore: update project configuration

- add .gitignore for knowledge directory
- update editor configuration
- improve build scripts
```

### Example 3: Tool Improvement
```
chore: improve development tools

- add pre-commit hooks
- update linting configuration
- improve test automation
```

## Best Practices
1. **Necessity**: Ensure tasks are truly necessary, avoid meaningless commits
2. **Impact Assessment**: Assess impact of configuration changes on project
3. **Documentation Updated**: Update relevant documentation if necessary
4. **Backward Compatible**: Ensure configuration changes don't break existing functionality