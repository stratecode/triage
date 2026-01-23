# Property Test Memory Issues - Diagnosis and Fix

## Problem

Los tests basados en propiedades (property-based tests) con Hypothesis se están bloqueando y consumiendo memoria excesiva. Esto indica bucles infinitos o generación descontrolada de datos.

## Root Causes Identified

### 1. Estrategias Recursivas Sin Límites

En varios archivos de test, las estrategias compuestas (`@st.composite`) están generando datos de forma recursiva sin límites claros:

**Ejemplo problemático en `test_plan_generation.py`:**
```python
@st.composite
def task_list_strategy(draw, min_size=0, max_size=20):
    """Generate a list of random JiraIssue objects with unique keys."""
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    tasks = []
    used_keys = set()
    
    for i in range(size):
        # Problema: Cada iteración puede generar más datos recursivamente
        task = draw(jira_issue_strategy(
            has_dependencies=has_deps if not is_admin else False,
            estimated_days=estimated_days,
            is_admin=is_admin,
            is_blocking=is_blocking
        ))
        
        # Problema: Este bucle while puede ser infinito si no hay suficientes claves únicas
        original_key = task.key
        counter = 0
        while task.key in used_keys:
            counter += 1
            task.key = f"{original_key}-{counter}"
        
        used_keys.add(task.key)
        tasks.append(task)
    
    return tasks
```

### 2. Generación de Texto Sin Restricciones

Las estrategias de generación de texto pueden crear strings muy largos:

```python
summary=draw(st.text(min_size=5, max_size=200)),
description=draw(st.text(min_size=0, max_size=500)),
```

Hypothesis puede generar caracteres Unicode complejos que consumen mucha memoria.

### 3. Estrategias Anidadas Profundas

Algunas estrategias llaman a otras estrategias que a su vez llaman a más estrategias:

```python
@st.composite
def daily_plan_strategy(draw):
    tasks = draw(task_list_strategy(min_size=3, max_size=15))
    # ... más generación
    plan = plan_generator.generate_daily_plan()
    return plan, tasks
```

### 4. Generación de Listas Sin Control

```python
issue_links=draw(st.lists(issue_link_strategy(), max_size=3)),
labels=draw(st.lists(st.text(min_size=1, max_size=20), max_size=5)),
```

## Solutions

### 1. Limitar Generación de Texto

Usar alfabetos restringidos y tamaños más pequeños:

```python
# ANTES (problemático)
project = draw(st.text(min_size=2, max_size=5, alphabet=st.characters(whitelist_categories=("Lu",))))

# DESPUÉS (mejor)
project = draw(st.text(
    min_size=2, 
    max_size=4,  # Reducido
    alphabet=st.characters(min_codepoint=65, max_codepoint=90)  # Solo A-Z
))

# ANTES (problemático)
summary=draw(st.text(min_size=5, max_size=200))

# DESPUÉS (mejor)
summary=draw(st.text(
    min_size=5, 
    max_size=50,  # Reducido significativamente
    alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))  # Sin caracteres de control
))
```

### 2. Simplificar Estrategias de Listas

```python
# ANTES (problemático)
@st.composite
def task_list_strategy(draw, min_size=0, max_size=20):
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    # ... generación compleja

# DESPUÉS (mejor)
@st.composite
def task_list_strategy(draw, min_size=0, max_size=10):  # Reducir max_size
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    # Usar builds() en lugar de generación manual
    return draw(st.lists(
        jira_issue_strategy(),
        min_size=min_size,
        max_size=max_size,
        unique_by=lambda x: x.key  # Hypothesis maneja unicidad
    ))
```

### 3. Usar `assume()` Para Filtrar

En lugar de bucles while infinitos:

```python
# ANTES (problemático)
while task.key in used_keys:
    counter += 1
    task.key = f"{original_key}-{counter}"

# DESPUÉS (mejor)
from hypothesis import assume
assume(task.key not in used_keys)
```

### 4. Reducir Profundidad de Anidamiento

```python
# ANTES (problemático)
@st.composite
def daily_plan_strategy(draw):
    tasks = draw(task_list_strategy(min_size=3, max_size=15))
    # ... más lógica compleja
    plan = plan_generator.generate_daily_plan()
    return plan, tasks

# DESPUÉS (mejor)
# Dividir en estrategias más simples y usar fixtures o helpers
```

### 5. Configurar Hypothesis Para Limitar Recursos

En `pytest.ini` o `pyproject.toml`:

```toml
[tool.pytest.ini_options]
hypothesis_profile = "default"

[tool.hypothesis]
max_examples = 50  # Reducir de 100
deadline = 5000  # 5 segundos por test
database = "none"  # Deshabilitar base de datos de ejemplos
```

### 6. Usar `@settings` Decorator

```python
from hypothesis import given, settings, strategies as st

@given(jira_issue_strategy())
@settings(
    max_examples=20,  # Menos ejemplos
    deadline=2000,  # 2 segundos timeout
    suppress_health_check=[HealthCheck.too_slow]  # Si es necesario
)
def test_property_3_task_classification_completeness(issue: JiraIssue):
    # ...
```

## Immediate Actions Required

1. **Reducir `max_size` en todas las estrategias de listas** de 20-30 a 5-10
2. **Limitar alfabetos de texto** a ASCII básico (A-Z, a-z, 0-9)
3. **Reducir `max_size` de strings** de 200-500 a 50-100
4. **Eliminar bucles while** y usar `assume()` o `unique_by`
5. **Configurar timeouts** en Hypothesis settings
6. **Reducir `max_examples`** de 100 a 20-50

## Testing the Fix

Después de aplicar los cambios:

```bash
# Ejecutar un solo test para verificar
uv run pytest tests/property/test_task_classification.py::test_property_3_task_classification_completeness -v

# Si funciona, ejecutar todos los property tests con timeout
uv run pytest tests/property/ -v --timeout=60

# Monitorear memoria
uv run pytest tests/property/ -v --memray
```

## Prevention

1. **Code review** de todas las estrategias de Hypothesis
2. **Establecer límites estrictos** en configuración de proyecto
3. **Monitorear tiempo de ejecución** de tests en CI/CD
4. **Usar perfiles de Hypothesis** para diferentes entornos (dev, CI)
