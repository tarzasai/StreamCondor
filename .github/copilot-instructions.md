## Development Environment

### Prerequisites

* **Python 3.12** or higher
* **pip** package manager
* **virtualenv** or **venv**
* **Git** for version control
* **PyQt6** for GUI components
* **streamlink** for livestream handling
* **argparse** for command-line argument parsing
* **BeautifulSoup4** for HTML parsing (to fetch favicons)
* **Pillow** for favicons processing and conversion

## Coding Standards

### Style Guide

**Follow PEP 8** with these specifics:

**Indentation**: 2 spaces (project convention)

**Line Length**: 120 characters max

**Naming Conventions**:
- `snake_case` for functions and variables
- `PascalCase` for classes
- `UPPER_CASE` for constants
- `_private_method` for private methods

**Example**:
```python
class SearchAssets(Job, AssetsOwnerJob):
  '''Main search orchestration job.'''

  MAX_RESULTS = 100

  def __init__(self, state, debug_info: bool = False):
    super().__init__(state, 'search')
    self.debug_info = debug_info

  async def _run(self) -> None:
    '''Execute search workflow.'''
    await self._run_search_jobs()
```

**Always use type hints** for function parameters and return values.

**Use Python 3.12 native syntax** - avoid `typing` module when possible:

```python
def process_assets(
  assets: list[Asset],
  threshold: float,
  options: dict[str, Any] | None = None
) -> list[Asset]:
  '''Filter assets by relevance threshold.'''
  return [a for a in assets if a.relevance >= threshold]
```

**Preferred**: Native types (`list`, `dict`, `set`, `tuple`) and union operator (`|`)

**Avoid**: `typing.List`, `typing.Dict`, `typing.Optional`, `typing.Union`

## Documentation

### Always use Mermaid diagrams for:
- Architecture overviews
- Data flows
- Sequence diagrams
- State machines
- Class hierarchies
- Component relationships

### Diagram Best Practices:
1. **Keep it simple** - One diagram per concept
2. **Use consistent styling** - Apply style directives for clarity
3. **Add descriptions** - Explain what the diagram shows
4. **Dark mode compatibility** - When applying colors to diagram elements, ALWAYS set both fill and color (text color) to ensure readability in dark mode:
   ```
   style Component fill:#e1f5e1,color:#000
   style ErrorNode fill:#ff6666,color:#fff
   ```
5. **Use appropriate types**:
   - `graph TD` / `graph LR` - High-level architecture
   - `sequenceDiagram` - API/process flows
   - `flowchart` - Business logic flows
   - `classDiagram` - Object models
   - `stateDiagram-v2` - State machines
   - `erDiagram` - Data models

### Example Complex Documentation Structure:
```
doc/
├── README.md (overview and TOC)
├── architecture.md (with 3-5 diagrams)
├── api-documentation.md (with sequence diagrams)
├── data-flow.md (with flowcharts)
├── integration.md (with integration diagrams)
├── deployment.md (with deployment diagrams)
├── monitoring.md
├── development.md (with class diagrams)
└── adr/
    ├── ADR-001-event-sourcing.md
    └── ADR-002-pubsub-integration.md
```

### Output Guidelines

1. **Be concise but comprehensive** - Include all necessary information without verbosity
2. **Use real values when available** - Extract actual URLs, versions, and configurations from the codebase
3. **Keep formatting consistent** - Follow the markdown style shown in examples
4. **Update existing content carefully** - Preserve working links and valid information
5. **Add placeholders where needed** - Use `{PROJECT_NAME}`, `{VERSION}`, etc. for unknown values
6. **Ensure all code blocks have language identifiers** - ```bash, ```java, ```python, etc.
7. **Cross-reference related documentation** - Link between README and doc/ files
8. **Make diagrams render-ready** - Test that Mermaid syntax is valid

### Special Considerations

- **For microservices**: Emphasize integration points and event flows
- **For APIs**: Include detailed endpoint documentation or link to Swagger
- **For libraries**: Include usage examples and API reference
- **For Cloud Run services**: Include GCP-specific deployment details
- **For event-driven systems**: Show event schemas and flow diagrams
- **For Java projects**: Always mention UNIT_TEST_COVERAGE environment variable
- **For projects with Okta**: Document authentication/authorization setup

### Validation Checklist

Before finalizing, ensure:
- [ ] All Mermaid diagrams render correctly
- [ ] All links are valid (or marked as TODO)
- [ ] Technology versions are accurate
- [ ] Prerequisites are complete and accurate
- [ ] Installation instructions work end-to-end
- [ ] Architecture diagram clearly shows the system
- [ ] If doc/ exists, extended documentation is comprehensive
- [ ] All sections are relevant to the specific project
- [ ] Code examples use correct syntax highlighting
- [ ] Project-specific details are included (not just templates)
