# Bug Fix Commit Template

## Template Description
For commits that fix code defects, errors, or issues.

## Commit Format
```
fix(<scope>): <brief description>

- <specific fix 1>
- <specific fix 2>
- <specific fix 3>

<optional: related issue or PR>
```

## Field Description
- **scope**: Optional, specifies the affected scope
- **brief description**: Under 50 words, describes the fixed issue
- **specific fixes**: Start with verbs, describe concrete fixes

## Examples

### Example 1: Fix Data Collection Issue
```
fix(collector): resolve data formatting issue

- fix JSON structure validation
- correct timestamp format
- improve error handling for invalid data

Fixes #23
```

### Example 2: Fix Analysis Logic Error
```
fix(analyzer): correct relevance scoring calculation

- fix scoring algorithm overflow
- improve precision for small values
- add boundary checks

Resolves #15
```

### Example 3: Fix Distribution Failure
```
fix(distributor): handle Telegram API rate limits

- implement exponential backoff retry
- add rate limit monitoring
- improve error messages
```

## Best Practices
1. **Root Cause**: Fix the root cause, not just symptoms
2. **Test Coverage**: Add tests to prevent recurrence
3. **Impact Analysis**: Assess impact on other components
4. **Documentation Updated**: Update documentation if necessary