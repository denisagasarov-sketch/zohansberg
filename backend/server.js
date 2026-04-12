const express = require('express')
const cors = require('cors')

const app = express()
const PORT = process.env.PORT || 3001

app.use(cors())
app.use(express.json())

// In-memory store
let tasks = []

const find = (id) => tasks.find((t) => t.id === id)

app.get('/tasks', (_req, res) => {
  res.json(tasks)
})

app.post('/tasks', (req, res) => {
  const { text } = req.body
  if (!text?.trim()) return res.status(400).json({ error: 'text required' })

  const active = tasks.filter((t) => !t.done)
  if (active.length >= 5) {
    return res.status(422).json({ error: 'max 5 active tasks' })
  }

  const task = {
    id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
    text: text.trim(),
    done: false,
    subtasks: [],
    createdAt: Date.now(),
  }
  tasks.push(task)
  res.status(201).json(task)
})

app.put('/tasks/:id', (req, res) => {
  const task = find(req.params.id)
  if (!task) return res.status(404).json({ error: 'not found' })
  Object.assign(task, req.body, { id: task.id, createdAt: task.createdAt })
  res.json(task)
})

app.delete('/tasks/:id', (req, res) => {
  const idx = tasks.findIndex((t) => t.id === req.params.id)
  if (idx === -1) return res.status(404).json({ error: 'not found' })
  tasks.splice(idx, 1)
  res.status(204).end()
})

app.listen(PORT, () => {
  console.log(`Backend → http://localhost:${PORT}`)
})
