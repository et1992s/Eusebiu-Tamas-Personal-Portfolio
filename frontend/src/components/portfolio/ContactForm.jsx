import { useState } from 'react';

import ScrollReveal from './ScrollReveal';

const INITIAL_FORM = {
  name: '',
  email: '',
  subject: '',
  message: '',
};

function ContactForm() {
  const [form, setForm] = useState(INITIAL_FORM);
  const [status, setStatus] = useState('idle');

  function handleChange(event) {
    const { name, value } = event.target;

    setForm((current) => ({
      ...current,
      [name]: value,
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();

    setStatus('submitting');

    try {
      const response = await fetch('/api/v1/contact', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(form),
      });

      if (!response.ok) {
        throw new Error('Contact request failed');
      }

      setForm(INITIAL_FORM);
      setStatus('success');
    } catch {
      setStatus('error');
    }
  }

  const isSubmitting = status === 'submitting';

  return (
    <form
      className="portfolio-contact-form"
      onSubmit={handleSubmit}
    >
      <ScrollReveal
        as="div"
        className="portfolio-contact-form-row"
        delay={0}
      >
        <label>
          Name
          <input
            type="text"
            name="name"
            value={form.name}
            onChange={handleChange}
            required
            autoComplete="name"
            placeholder="Your name"
          />
        </label>

        <label>
          Email
          <input
            type="email"
            name="email"
            value={form.email}
            onChange={handleChange}
            required
            autoComplete="email"
            placeholder="you@example.com"
          />
        </label>
      </ScrollReveal>

      <ScrollReveal
        as="label"
        delay={120}
      >
        Subject
        <input
          type="text"
          name="subject"
          value={form.subject}
          onChange={handleChange}
          required
          placeholder="What would you like to discuss?"
        />
      </ScrollReveal>

      <ScrollReveal
        as="label"
        delay={240}
      >
        Message
        <textarea
          name="message"
          value={form.message}
          onChange={handleChange}
          required
          rows={7}
          placeholder="Tell me a little about your project, opportunity or idea..."
        />
      </ScrollReveal>

      <ScrollReveal
        as="div"
        className="portfolio-contact-form-footer"
        delay={360}
      >
        <button
          type="submit"
          disabled={isSubmitting}
        >
          {isSubmitting ? 'Sending...' : 'Send message'}
        </button>

        {status === 'success' && (
          <p className="portfolio-contact-form-status portfolio-contact-form-status-success">
            Your message has been sent successfully.
          </p>
        )}

        {status === 'error' && (
          <p className="portfolio-contact-form-status portfolio-contact-form-status-error">
            Something went wrong. Please try again.
          </p>
        )}
      </ScrollReveal>
    </form>
  );
}

export default ContactForm;
