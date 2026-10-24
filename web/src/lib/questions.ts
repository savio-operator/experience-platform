export type Answers = {
  when?: string; where?: string; who?: string; occasion?: string;
  budget?: number; kind?: string; constraints?: string; transport?: string;
};
export type QuestionId = keyof Answers;
type Question = { id: QuestionId; title: string; hint: string; type: "choice" | "budget" | "text"; choices?: string[]; placeholder?: string };

export const questions: Question[] = [
  { id: "when", title: "When shall we head out?", hint: "A little spontaneity, on your schedule.", type: "choice", choices: ["Now · next 2 hours", "This evening · before 7 pm", "Tonight · after 7 pm"] },
  { id: "where", title: "Which part of Kochi?", hint: "Pick the area you’d like to explore.", type: "choice", choices: ["Fort Kochi", "Panampilly Nagar", "Marine Drive", "Kakkanad", "Edappally", "Anywhere in Kochi"] },
  { id: "who", title: "Who’s coming along?", hint: "Good company includes your own.", type: "choice", choices: ["Just me", "Two of us", "A small group · 3–4", "A bigger group · 5+"] },
  { id: "occasion", title: "What’s the occasion?", hint: "An ordinary evening is a perfectly good reason.", type: "choice", choices: ["No occasion, just because", "Catching up", "A little celebration", "Time to unwind"] },
  { id: "budget", title: "What feels comfortable?", hint: "Your total budget for everyone, in rupees. Nothing is charged.", type: "budget", placeholder: "Enter your total budget" },
  { id: "kind", title: "What are you in the mood for?", hint: "Choose the feeling you’d like the evening to have.", type: "choice", choices: ["Something calm", "Something creative", "Something outdoors", "Something delicious", "Surprise me"] },
  { id: "constraints", title: "Anything we should keep in mind?", hint: "Dietary needs, accessibility, no alcohol, or anything else. Type “None” if there’s nothing to add.", type: "text", placeholder: "For example: vegetarian, step-free access…" },
  { id: "transport", title: "How would you like to get there?", hint: "Tell us your preference. Transport is not booked in this demo.", type: "choice", choices: ["I have my own transport", "I’ll take a taxi", "Public transport", "Walking distance only", "No preference"] },
];

export function isComplete(answers: Answers) {
  return questions.every(({ id }) => id === "budget"
    ? typeof answers.budget === "number" && answers.budget > 0
    : typeof answers[id] === "string" && (answers[id] as string).trim().length > 0);
}
