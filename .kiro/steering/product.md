# Product Overview

The AI Secretary is an execution support system for senior technical professionals working in high-interruption, multi-project environments. It reduces cognitive load by generating focused daily plans with a maximum of 3 real priorities.

## Core Principles

- **JIRA as Single Source of Truth**: No persistent local state; all task data lives in JIRA
- **Human Control**: Every plan and action requires explicit user approval
- **Cognitive Load Minimization**: Maximum 3 priorities per day, grouped administrative tasks
- **Daily Closure Focus**: All priority tasks must be closable within one working day
- **Asynchronous Operation**: Background polling and plan generation without blocking the user

## Key Features

- Daily plan generation with up to 3 priority tasks
- Task classification by urgency, effort, and dependencies
- Administrative task grouping into low-energy time blocks
- Blocking task detection and re-planning
- Long-running task decomposition into daily-closable units
- Structured markdown output for easy parsing and sharing
