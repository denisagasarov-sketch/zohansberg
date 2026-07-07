// Палитра направлений v2 — приглушённые тёплые тона, гармонирующие с янтарным акцентом
const PALETTE = [
  '#7286c8', // синий
  '#7fa878', // зелёный
  '#c98d5a', // оранжевый
  '#b87a9e', // розовый
  '#6aa8ad', // бирюзовый
  '#9a7fc2', // фиолетовый
  '#a8a35e', // жёлто-зелёный
]

export function getDirectionColor(directionId: number): string {
  return PALETTE[(directionId - 1) % PALETTE.length]
}
