---
name: nasareqs
description: Write, review, or critique engineering/system/software requirements against NASA's "How to Write a Good Requirement" checklist. Use when drafting requirements, reviewing a requirements document, checking whether a "shall" statement is clear/complete/verifiable, or resolving ambiguity, TBDs, or unverifiable terms.
---

# How to Write a Good Requirement

Source: NASA, "Appendix C: How to Write a Good Requirement" (public domain, US government work).
<https://www.nasa.gov/reference/appendix-c-how-to-write-a-good-requirement/>

Use the checklists below when authoring or reviewing requirements. Apply them item by item; flag any requirement that fails a check.

## C.1 Use of Correct Terms

- **Shall** = requirement
- **Will** = facts or declaration of purpose
- **Should** = goal

## C.2 Editorial Checklist

### Personnel Requirement

Requirements should use active voice stating "responsible party shall perform such and such." The requirement identifies who shall act followed by a description of what should be performed.

### Product Requirement

- The requirement takes the form "product ABC shall XYZ"
- Consistent terminology refers to the product and its lower-level entities
- Tolerances are complete for qualitative/performance values (e.g., less than, greater than or equal to, plus or minus, 3 sigma root sum squares)
- The requirement is free of implementation details (stating WHAT is needed, NOT HOW)
- No descriptions of operations are included (operational statements belong elsewhere)

### Example Product Requirements

- The system shall operate at a power level of…
- The software shall acquire data from the…
- The structure shall withstand loads of…
- The hardware shall have a mass of…

## C.3 General Goodness Checklist

- Grammatically correct
- Free of typos, misspellings, and punctuation errors
- Complies with project's template and style rules
- Stated positively rather than negatively
- Minimizes "To Be Determined" (TBD) values; uses best estimates marked "To Be Resolved" (TBR) with rationale
- Accompanied by intelligible rationale including assumptions
- Located in proper document section

## C.4 Requirements Validation Checklist

### Clarity

- Requirements are clear and unambiguous without indefinite pronouns or ambiguous terms
- Requirements are concise and simple
- Each requirement expresses only one thought
- Requirement statement has one subject and one predicate

### Completeness

- Requirements stated as completely as possible with TBDs/TBRs maintained
- No missing requirements (functional, performance, interface, environment, facility, transportation, training, personnel, operability, safety, security, appearance, physical characteristics, design)
- All assumptions explicitly stated

### Compliance

- All requirements at correct level (system, segment, element, subsystem)
- Free of implementation specifics
- Free of operational descriptions
- Free of personnel or task assignments

### Consistency

- Requirements stated consistently without contradictions
- Terminology consistent with user, sponsor, and project glossary
- Key terms included in project glossary

### Traceability

- All requirements necessary to meet parent requirement
- Bidirectionally traceable to higher-level requirements or mission scope
- Uniquely referenced (each requirement numbered)

### Correctness

- Each requirement is correct
- All stated assumptions are correct and confirmed before baselining
- Requirements are technically feasible

### Functionality

- All functions necessary and sufficient to meet mission and system goals and objectives

### Performance

- All required performance specifications and margins listed (timing, throughput, storage, latency, accuracy, precision)
- Each performance requirement realistic
- Tolerances defendable and cost-effective

### Interfaces

- All external interfaces clearly defined
- All internal interfaces clearly defined
- All interfaces necessary, sufficient, and consistent

### Maintainability

- Requirements for system maintainability specified in measurable, verifiable manner
- Requirements written to minimize ripple effects from changes

### Reliability

- Clearly defined, measurable, verifiable reliability requirements specified
- Error detection, reporting, handling, and recovery requirements included
- Undesired events considered with required responses specified
- Assumptions about intended function sequences stated
- Requirements adequately address survivability after software or hardware faults

### Verifiability/Testability

- System can be tested, demonstrated, inspected, or analyzed to show satisfaction of requirements
- Requirements stated precisely for test success criteria specification
- Free of unverifiable terms (flexible, easy, sufficient, safe, ad hoc, adequate, accommodate, user-friendly, usable, when required, if required, appropriate, fast, portable, light-weight, small, large, maximize, minimize, robust, quickly, easily, clearly)

### Data Usage

- "Don't care" conditions truly irrelevant where applicable
- "Don't care" condition values explicitly stated
