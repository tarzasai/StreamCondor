# StreamCondor Documentation

Complete documentation for the StreamCondor livestream monitoring application.

## Quick Links

- [README](../README.md) - Project overview, installation, quick start
- [CONTRIBUTING](../CONTRIBUTING.md) - Contribution guidelines
- [LICENSE](../LICENSE) - MIT License

## Documentation Structure

### Core Documentation

1. **[Architecture Overview](architecture.md)**
   - System architecture and component design
   - Core components (Configuration, Monitor, Launcher, Favicons)
   - UI components (TrayIcon, Settings, Stream Dialog)
   - Data flow and thread model
   - Resource management
   - Design decisions and future enhancements

2. **[Data Flow](data-flow.md)**
   - Configuration flow (load, save, modifications)
   - Stream monitoring flow (periodic checks, status detection)
   - Stream launch flow (command building, argument merging)
   - Notification flow (tristate logic, platform handling)
   - Favicon loading flow (caching, resizing)
   - Performance optimizations

3. **[Development Guide](development.md)**
   - Getting started with development
   - Project structure and module dependencies
   - Development workflow and branching
   - Coding standards (PEP 8, type hints, docstrings)
   - Testing guidelines
   - Debugging techniques
   - Building and packaging

4. **[Configuration Reference](configuration.md)**
   - Complete configuration file format
   - Global settings (monitoring, notifications, streamlink, player, UI)
   - Stream configuration (required and optional fields)
   - Advanced options (window geometry, variable substitution)
   - Configuration examples (minimal to advanced)
   - Migration guide and troubleshooting

## Documentation Features

### Mermaid Diagrams

All documentation includes comprehensive diagrams:
- **Architecture diagrams** - Component relationships and dependencies
- **Sequence diagrams** - Interaction flows between components
- **Flowcharts** - Process flows and decision trees
- **State diagrams** - UI state transitions
- **Class diagrams** - Data structures and relationships

### Dark Mode Compatible

All diagrams use proper color styling with both `fill` and `color` attributes to ensure readability in light and dark modes.

### Code Examples

Every section includes practical code examples with:
- Syntax highlighting
- Type hints using Python 3.12 native syntax
- Clear comments and explanations
- Real-world use cases

## For Users

### Getting Started

1. Read the [README](../README.md) for:
   - Installation instructions
   - Quick start guide
   - Basic usage

2. Refer to [Configuration Reference](configuration.md) for:
   - Setting up streams
   - Customizing behavior
   - Troubleshooting configuration issues

### Advanced Usage

- **Customizing notifications** - See tristate notification logic in [Configuration Reference](configuration.md#notify)
- **Variable substitution** - Use `$SC.name` and `$SC.type` in arguments (see [Configuration Reference](configuration.md#variable-substitution))
- **Multi-platform setup** - Examples in [Configuration Reference](configuration.md#multi-platform-configuration)

## For Developers

### Understanding the Codebase

1. Start with [Architecture Overview](architecture.md) to understand:
   - Overall system design
   - Component responsibilities
   - Thread model
   - Design decisions

2. Read [Data Flow](data-flow.md) to understand:
   - How data moves through the application
   - Interaction patterns between components
   - Caching and optimization strategies

3. Follow [Development Guide](development.md) for:
   - Setting up development environment
   - Coding standards and conventions
   - Testing and debugging
   - Build and packaging

### Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for:
- Code of conduct
- How to report bugs
- Feature request process
- Pull request guidelines
- Code review process

## Documentation Standards

### Writing Style

- **Concise** - Clear and to the point
- **Complete** - Cover all necessary details
- **Practical** - Include examples and use cases
- **Accessible** - Understandable for various skill levels

### Code Formatting

All code examples follow project standards:
- **2-space indentation**
- **120 character line length**
- **Python 3.12 native type hints**
- **Descriptive variable names**

### Diagram Standards

- **Clear labels** - Descriptive component names
- **Consistent colors** - Same colors for same component types
- **Dark mode support** - Both fill and color attributes set
- **Focused scope** - One concept per diagram

## Building Documentation

### Preview Mermaid Diagrams

Use VS Code with Mermaid extension or online tools:
- [Mermaid Live Editor](https://mermaid.live/)
- VS Code Preview (Ctrl+Shift+V or Cmd+Shift+V)

### Generating HTML Documentation

```bash
# Using markdown renderers
pip install markdown
python -m markdown README.md > README.html

# Or use pandoc
pandoc README.md -o README.html
```

### PDF Generation

```bash
# Using pandoc with LaTeX
pandoc README.md -o README.pdf

# Or use markdown-pdf
npm install -g markdown-pdf
markdown-pdf README.md
```

## Documentation Checklist

When updating documentation:

- [ ] All Mermaid diagrams render correctly
- [ ] Code examples use correct syntax highlighting
- [ ] Links to other documents work
- [ ] Dark mode colors properly set (fill + color)
- [ ] Type hints use Python 3.12 native syntax
- [ ] Indentation follows project standard (2 spaces)
- [ ] Line length under 120 characters
- [ ] Examples are tested and accurate
- [ ] No broken internal references

## Feedback and Improvements

Documentation is always evolving. Help us improve:

- **Report issues** - Unclear sections, errors, or omissions
- **Suggest additions** - Missing topics or examples
- **Fix typos** - Even small improvements matter
- **Add diagrams** - Visual explanations help understanding

See [CONTRIBUTING.md](../CONTRIBUTING.md) for how to submit improvements.

---

**Last Updated**: 2024 (Version 1.0.0)
