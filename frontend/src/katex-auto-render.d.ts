declare module "katex/contrib/auto-render" {
  type Delimiter = {
    left: string;
    right: string;
    display: boolean;
  };

  type AutoRenderOptions = {
    delimiters?: Delimiter[];
    throwOnError?: boolean;
  };

  export default function renderMathInElement(
    element: HTMLElement,
    options?: AutoRenderOptions,
  ): void;
}
