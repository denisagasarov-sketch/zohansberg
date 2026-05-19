const PALETTE = [
  '#6070c0', // синий
  '#50a068', // зелёный
  '#c07840', // оранжевый
  '#a05090', // розовый
  '#40a0b0', // бирюзовый
  '#9060c0', // фиолетовый
  '#a0a040', // жёлто-зелёный
]

export function getDirectionColor(directionId: number): string {
  return PALETTE[(directionId - 1) % PALETTE.length]
}
