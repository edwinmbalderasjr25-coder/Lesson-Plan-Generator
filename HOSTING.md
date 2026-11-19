# Publishing the Lesson Plan Maker for free

This folder is a complete website (no server needed). Upload it to a free static host and teachers open the link.
Menu names on these sites change from time to time, so follow the idea if a label looks different.

## A. Publish on GitHub Pages (free)
1. Create a free account at github.com.
2. Click **New repository**. Name it `lesson-plan-maker`. Choose **Public**. Create it.
3. In the repository click **Add file > Upload files**. Drag in everything inside this folder:
   `index.html` and the `js`, `py` and `data` folders (drag the folders themselves). Click **Commit changes**.
4. Open **Settings > Pages**. Under "Build and deployment" choose **Deploy from a branch**, branch **main**, folder **/ (root)**, then **Save**.
5. Wait a minute or two. The page shows your link, usually `https://YOUR-USERNAME.github.io/lesson-plan-maker/`.
6. Open the link, fill in a test week, and check that the Word engine chip at the top turns green ("ready").

Because the repository is public, the template, competency list and code are public. They contain no keys and no personal data.
Never upload a file that contains someone's API key.

## B. Get a free AI key (only for the automatic method)
1. Sign in to Google AI Studio (aistudio.google.com) with a Google account.
2. Choose **Get API key** and create a key. No payment details should be needed for the free tier.
3. In the app choose "Free Google AI Studio key", paste the key, and draft.
4. If the app says the model is not found, open the model list in AI Studio, copy a current free model name, and type it in the "Model name" box.
Free limits and which models are free change over time and are shown in AI Studio.

## C. Teachers who do not want a key
Choose **Paste-in**. The app writes the request; paste it into any free AI chat; paste the JSON answer back.

## D. Updating the competencies or the template
- Replace `data/competencies.json` (made from the Excel database) or `data/template.docx` in the repository (**Add file > Upload files**, same name). The site updates in a minute.

## E. Privacy
- Teacher details and the key are stored in each teacher's own browser (localStorage), not on any server of yours.
- The AI sees the competencies, dates and notes you type. Do not type learner names. Google says free-tier requests may be used to improve its products.
- On a shared computer, do not tick "Remember the key", and use "Remove saved key" when finished.
