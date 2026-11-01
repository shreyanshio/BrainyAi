import React from 'react'

export type BrainyLogoVariant =
  | 'wordmark'
  | 'symbol'
  | 'app-icon'
  | 'light-symbol'
  | 'dark-symbol'
  | 'mobile-wordmark'

export interface BrainyLogoProps extends React.ImgHTMLAttributes<HTMLImageElement> {
  variant?: BrainyLogoVariant
  alt?: string
  className?: string
  priority?: boolean
  width?: number | string
  height?: number | string
}

const LOGO_CONFIGS: Record<
  BrainyLogoVariant,
  {
    src: string
    defaultWidth: number
    defaultHeight: number
    defaultAlt: string
  }
> = {
  wordmark: {
    // Uses the precision-fitted horizontal wordmark (aspect ratio 3:1, zero dead bottom margin)
    src: '/brand/brainy-web-desktop.png',
    defaultWidth: 360,
    defaultHeight: 120,
    defaultAlt: 'Brainy',
  },
  'mobile-wordmark': {
    // Compact mobile lockup optimized for smaller viewports (height 80px retina)
    src: '/brand/brainy-web-mobile.png',
    defaultWidth: 240,
    defaultHeight: 80,
    defaultAlt: 'Brainy',
  },
  symbol: {
    // Compact standalone symbol (1:1 square canvas)
    src: '/brand/brainy-symbol-opt.png',
    defaultWidth: 128,
    defaultHeight: 128,
    defaultAlt: 'Brainy AI',
  },
  'app-icon': {
    // Official squircle application and profile launcher icon
    src: '/brand/brainy-app-icon.png',
    defaultWidth: 256,
    defaultHeight: 256,
    defaultAlt: 'Brainy app icon',
  },
  'light-symbol': {
    // Primary black logo on light surface
    src: '/brand/brainy-primary-black-logo.png',
    defaultWidth: 280,
    defaultHeight: 305,
    defaultAlt: 'Brainy symbol',
  },
  'dark-symbol': {
    // White logo on solid black container
    src: '/brand/brainy-white-logo-on-black.png',
    defaultWidth: 261,
    defaultHeight: 305,
    defaultAlt: 'Brainy symbol',
  },
}

export function BrainyLogo({
  variant = 'wordmark',
  alt,
  className = '',
  priority = false,
  width,
  height,
  style,
  ...rest
}: BrainyLogoProps) {
  const config = LOGO_CONFIGS[variant] || LOGO_CONFIGS.wordmark
  const inkMode = variant === 'app-icon' ? undefined : variant === 'dark-symbol' ? 'light' : 'dark'

  return (
    <img
      src={config.src}
      alt={alt ?? config.defaultAlt}
      width={width ?? config.defaultWidth}
      height={height ?? config.defaultHeight}
      loading={priority ? 'eager' : 'lazy'}
      decoding={priority ? 'sync' : 'async'}
      className={`brainy-logo-image select-none object-contain ${className}`}
      style={{
        aspectRatio: `${config.defaultWidth} / ${config.defaultHeight}`,
        ...style,
      }}
      {...rest}
      data-brainy-logo-ink={inkMode}
    />
  )
}
