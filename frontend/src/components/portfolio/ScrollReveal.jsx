import useScrollReveal from '../../hooks/useScrollReveal';

function ScrollReveal({
  children,
  className = '',
  delay = 0,
  as: Component = 'div',
  ...props
}) {
  const revealRef = useScrollReveal();

  return (
    <Component
      ref={revealRef}
      className={`portfolio-reveal ${className}`.trim()}
      style={{
        '--portfolio-reveal-delay': `${delay}ms`,
      }}
      {...props}
    >
      {children}
    </Component>
  );
}

export default ScrollReveal;