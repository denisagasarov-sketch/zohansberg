import { Component, type ReactNode } from 'react'

interface Props { children: ReactNode; fallback?: ReactNode }
interface State { error: Error | null }

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }
  static getDerivedStateFromError(error: Error) { return { error } }
  componentDidCatch(error: Error) { console.error('[ErrorBoundary]', error) }
  render() {
    if (this.state.error) {
      return this.props.fallback ?? (
        <div className="text-[11px] text-[#9c958a] p-4 text-center">
          Не удалось загрузить мини-игру.
          <div className="text-[9px] text-[#453f37] mt-1">{String(this.state.error.message)}</div>
        </div>
      )
    }
    return this.props.children
  }
}
