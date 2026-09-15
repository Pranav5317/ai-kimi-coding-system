---
name: mongodb-mongoose
description: MongoDB document schema design, Mongoose models, indexes, schema validation, and aggregation pipelines.
target_agent: agent3
---

# MongoDB & Mongoose Database Skill

When designing NoSQL document schemas or MongoDB queries:

## Key Guidelines
1. **Mongoose Schema Design**:
   - Define Mongoose schemas (`new Schema({...}, { timestamps: true })`).
   - Enforce field types, default values, required fields, and index definitions (`index: true`).

2. **Querying & Aggregation**:
   - Use Mongoose model helper methods (`find()`, `findOne()`, `findByIdAndUpdate()`).
   - Build multi-stage aggregation pipelines (`model.aggregate([...])`) for complex analytics and data transformations.

