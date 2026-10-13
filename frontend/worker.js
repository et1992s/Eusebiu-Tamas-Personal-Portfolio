function jsonResponse(body, status = 200) {
  return Response.json(body, {
    status,
    headers: {
      "Cache-Control": "no-store",
    },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname !== "/api/v1/contact") {
      return env.ASSETS.fetch(request);
    }

    if (request.method !== "POST") {
      return jsonResponse(
        { success: false, message: "Method not allowed." },
        405,
      );
    }

    let body;

    try {
      body = await request.json();
    } catch {
      return jsonResponse(
        { success: false, message: "Invalid JSON request." },
        400,
      );
    }

    const name =
      typeof body?.name === "string" ? body.name.trim() : "";
    const email =
      typeof body?.email === "string" ? body.email.trim() : "";
    const subject =
      typeof body?.subject === "string" ? body.subject.trim() : "";
    const message =
      typeof body?.message === "string" ? body.message.trim() : "";

    const validEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

    if (
      name.length < 2 ||
      name.length > 100 ||
      !validEmail ||
      email.length > 254 ||
      subject.length < 3 ||
      subject.length > 200 ||
      message.length < 10 ||
      message.length > 5000
    ) {
      return jsonResponse(
        {
          success: false,
          message: "Please check your contact details and message.",
        },
        400,
      );
    }

    const apiKey = env.RESEND_API_KEY;
    const toEmail = env.CONTACT_TO_EMAIL;
    const fromEmail = env.CONTACT_FROM_EMAIL;

    if (!apiKey || !toEmail || !fromEmail) {
      console.error("Contact service configuration is incomplete.");

      return jsonResponse(
        {
          success: false,
          message: "The contact service is temporarily unavailable.",
        },
        503,
      );
    }

    const emailText = [
      "New portfolio contact message",
      "",
      `Name: ${name}`,
      `Email: ${email}`,
      `Subject: ${subject}`,
      "",
      "Message:",
      message,
    ].join("\n");

    try {
      const response = await fetch("https://api.resend.com/emails", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          from: fromEmail,
          to: [toEmail],
          reply_to: email,
          subject: `Portfolio enquiry: ${subject}`,
          text: emailText,
        }),
      });

      if (!response.ok) {
        console.error(
          "Resend rejected the contact request.",
          "HTTP status:",
          response.status,
        );

        return jsonResponse(
          {
            success: false,
            message: "We could not send your message right now.",
          },
          502,
        );
      }

      return jsonResponse({
        success: true,
        message: "Contact request received.",
      });
    } catch (error) {
      console.error("Contact email request failed:", error);

      return jsonResponse(
        {
          success: false,
          message: "We could not send your message right now.",
        },
        502,
      );
    }
  },
};
