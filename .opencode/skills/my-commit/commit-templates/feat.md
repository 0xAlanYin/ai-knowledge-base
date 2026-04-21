# Feature Addition Commit Template

## Template Description
For commits that add new features, modules, or capabilities.

## Commit Format
```
feat(<scope>): <brief description>

- <specific implementation point 1>
- <specific implementation point 2>
- <specific implementation point 3>

<optional: related issue or PR>
```

## Field Description
- **scope**: Optional, specifies the affected scope (e.g., collector, analyzer, distributor)
- **brief description**: Under 50 words, describes the new feature
- **specific implementation points**: Start with verbs, describe concrete implementation details

## Examples

### Example 1: New Collection Feature
```
feat(collector): add GitHub trending data collection

- implement websearch-based data collection
- add data validation and formatting
- update AGENTS.md with practical experience

Closes #42
```

### Example 2: New Analysis Feature
```
feat(analyzer): add AI content analysis

- implement content categorization
- add relevance scoring algorithm
- integrate with domestic large models
```

### Example 3: New Distribution Feature
```
feat(distributor): add Telegram notification

- implement Telegram Bot API integration
- add message templating system
- support scheduled notifications
```

## Best Practices
1. **Atomicity**: One commit implements one complete feature
2. **Testable**: New features should include appropriate tests
3. **Documentation Updated**: Update relevant documentation for new features
4. **Backward Compatible**: Ensure new features don't break existing functionality