export type Answers = {
  when?: string; where?: string; who?: string; occasion?: string;
  budget?: number; kind?: string; constraints?: string; transport?: string;
};
export type QuestionId = keyof Answers;
type Question = { id: QuestionId; title: string; hint: string; type: "budget" | "text"; placeholder: string };

export const questions: Question[] = [
  { id: "when", title: "When would you like to go?", hint: "Tell me your preferred date and time, in your own words.", type: "text", placeholder: "Tomorrow around 8:30 pm, or Saturday after lunch…" },
  { id: "where", title: "Where in Kochi would you like to be?", hint: "Any neighbourhood, a nearby landmark, or anywhere in Kochi is fine.", type: "text", placeholder: "Somewhere near Fort Kochi, within a short drive…" },
  { id: "who", title: "Who’s coming along?", hint: "Tell me how many people and anything I should know about your group.", type: "text", placeholder: "Three friends and me…" },
  { id: "occasion", title: "What’s the occasion?", hint: "It can be a celebration, a catch-up, or simply time for yourself.", type: "text", placeholder: "A quiet evening together, no special occasion…" },
  { id: "budget", title: "What total budget feels comfortable?", hint: "Your budget for everyone, in rupees. Nothing is charged.", type: "budget", placeholder: "₹500 total for everyone…" },
  { id: "kind", title: "What kind of experience are you imagining?", hint: "Describe the feeling, activity or idea you have in mind.", type: "text", placeholder: "Something outdoors and relaxed, maybe near the water…" },
  { id: "constraints", title: "Anything else I should keep in mind?", hint: "Dietary needs, accessibility, things to avoid, or “none” if there’s nothing to add.", type: "text", placeholder: "Vegetarian food, step-free access, no alcohol…" },
  { id: "transport", title: "How would you like to get there?", hint: "Describe your transport preference. Transport is not booked in this preview.", type: "text", placeholder: "We’ll drive, but I’d rather avoid a long journey…" },
];

export function isComplete(answers: Answers) {
  return questions.every(({ id }) => id === "budget"
    ? typeof answers.budget === "number" && answers.budget > 0
    : typeof answers[id] === "string" && (answers[id] as string).trim().length > 0);
}
