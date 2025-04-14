/*
this file is for dealing with all the operation of the local database for the chat
*/

/*
Setup localDBs
*/
const issuesDB = new PouchDB("issues");

/*
Code logic
*/
function jaffar() {
  return {
    demoMode: true,
    author: '',
    version: 1,
    page: "login",
    newMessage: "",
    messages: [],
    questions: [],
    questionIndex: -1,
    alert: "",
    missingFields: [],
    answers: {},
    issues: {},
    searchInput: "",
    async init() {
    await this.getAuth()
    this.page = this.author.length>0  ? "loading" : "login";
    if (this.page!="login"){
    this.questions = await getConfig()
     this.$watch("answers", (value, oldValue) =>
          this.updateAnswers(value, oldValue)
        );
     await this.getAllLocalDBIssues();
     this.page="form-slideshow"
    }
    },
    async newUserMessage(message, role) {
      doc = setNewMessage(message, role);
      await saveMessage(doc);
      this.messages.push(doc);
      scroll();
      doc = setJaffarThinking();
      this.messages.push(doc);
      scroll();
      jaffarAnswer = await callJaffar(message, this.messages);
      doc = setNewMessage(jaffarAnswer, "jaffar");
      this.messages.pop();
      await saveMessage(doc);
      this.messages.push(doc);
      scroll();
    },
    async deleteChat() {
      // await chatDB.destroy();
      // chatDB = await new PouchDB("chatDB");
      // return (this.messages = []);
    },
    showFormPage() {
      window.location.reload();
    },
    getJaffarConfig() {
      let exportJaffarConfig = {};
      exportJaffarConfig._id = "jaffarConfig";
      exportJaffarConfig.questions = this.questions;
      return JSON.stringify(exportJaffarConfig);
    },
    saveAnswer(key, value) {
      if (!this.answers[key]) {
        this.answers[key] = [];
      }
      let index = this.answers[key].indexOf(value);
      index != -1
        ? this.answers[key].splice(index, 1)
        : this.answers[key].push(value);
    },
    setOpenIssuesGrid() {
      setOpenIssuesGrid(this.issues);
    },
    async updateAnswers() {
      this.answers._id && (await this.saveIssueLocalDB());
      this.answers._id && this.isIssueFullyValid();
      this.answers._id && this.saveAnswersInGlobalDB();
    },
    isIssueFullyValid() {
      if (this.answers.status != "Sent") {
        const missingFields = [];
        const answers = this.answers;
        this.questions.forEach(({ key, required }) => {
          if (required) {
            if (
              !key in answers ||
              answers[key] == "" ||
              answers[key] == undefined ||
              Array.isArray(answers[key] && answers[key].length == 0)
            ) {
              missingFields.push(key);
            }
          }
        });
        this.missingFields = missingFields;
        console.log(this.missingFields.length == 0 ? "Complete" : "Incomplete");
        this.missingFields.length == 0
          ? (this.answers.status = "Complete")
          : (this.answers.status = "Incomplete");
        return this.missingFields.length == 0 ? "Complete" : "Incomplete";
      }
    },
    async createANewForm() {
      const id = "JAF-ISS-" + new Date().getTime();
      this.answers._id = id;
      this.answers.createdAt = new Date().toISOString();
      if (this.author) {
        this.answers.author = this.author;
      }
      res = await issuesDB.put({ ...this.answers });
      await this.getAllLocalDBIssues();
    },
    async saveIssueLocalDB() {
      console.log("save called", Alpine.raw(this.answers));
      rev = await issuesDB.get(this.answers._id);
      answers = { ...this.answers };
      answers._rev = rev["_rev"];
      return await issuesDB.put(answers);
    },
    async getAllLocalDBIssues() {
      console.log("call all from issues DB");
      myIssues = await issuesDB.allDocs({ include_docs: true });
      issues = [];
      myIssues.rows.forEach((x) => issues.push(x.doc));
      this.issues = issues.reverse();
    },
    async deleteIssue(id) {
      console.log(`delete ${id}`);
      answer = await issuesDB.get(id);
      await issuesDB.remove(answer);
      return this.getAllLocalDBIssues();
    },
    async selectIssue(id) {
      console.log(`get ${id}`);
      savedAnswers = await issuesDB.get(id);
      console.log(savedAnswers);
      for (const key in savedAnswers) {
        if (savedAnswers.hasOwnProperty(key)) {
          this.answers[key] =
            savedAnswers[key] != " - " ? savedAnswers[key] : "";
          console.log(this.answers[key]);
        }
      }

      this.page = "send-issue-page";
    },
    async submitAnswersInGlobalDB() {
       if (this.demoMode){ return alert('DEMO MODE ACTIVATED. YOUR REQUEST IS NOT SUBMITTED TO JAFFAR')}
             if (!this.author) {
        setAuth(this.answers.author);
      }
      this.answers.submitedAt = new Date().toISOString();
      this.answers.status = "Sent";
      this.answers.configs={}
      this.answers.configs.questions=await getCurrentConfigNames("jaffarConfig")
      this.answers.configs.templates=await getCurrentConfigNames("jaffarTemplates")
      this.answers.configs.rules =await getCurrentConfigNames("jaffarRules")
      this.answers.configs.escalation =await getCurrentConfigNames("jaffarEscalationRules")
      this.answers.configs.directories=await getCurrentConfigNames("jaffarDirectories")
       await axios.post(
        `/pc-analytics-jaffar/jaffar/issues/submit`,
        { obj: { answers: this.answers } }
      );
      window.location.reload();
    },
    async saveAnswersInGlobalDB() {
      await axios.post(
        `/pc-analytics-jaffar/jaffar/issues/save`,
        { obj: { answers: this.answers } }
      );
    },
   async getAuth() {
   console.log("getAuth")
       this.author = await window.localStorage.getItem("author") || "";
       console.log("author: ",this.author)
    },
    async setAuth() {
    console.log("setAuth")
     await window.localStorage.setItem("author", this.author);
     await this.getAuth()
     window.location.reload()
    }
  };
}

//////////////////////////////////////////////////
// ##############################################
/////////////////////////////////////////////////

// HELPERS

//////////////////////////////////////////////////
// ##############################################
/////////////////////////////////////////////////

// set the new message object
function setNewMessage(message, role) {
  const doc = {
    _id: new Date().toISOString(),
    text: message,
    role: role,
    date: new Date().toLocaleString("en-GB"),
  };

  return doc;
}

// Save a message
async function saveMessage(doc) {
  // return await chatDB.put(doc);
}

// get all messages
function getMessages() {
  // return chatDB.allDocs({ include_docs: true }).then((result) => {
  //   return result.rows.map((row) => row.doc);
  // });
}

// set the Jaffar thinking animation

function setJaffarThinking() {
  const doc = {
    _id: new Date().toISOString(),
    text: "...",
    role: "thinking-jaffar",
  };
  return doc;
}

async function callJaffar(question, messages) {
  jaffarAnswer = await axios.post(
    "http://localhost:8000/api/pc-analytics-jaffar-svc/invoke_jaffar",
    {
      history: messages,
    },
    {
      headers: {
        accept: "application/json",
        "Content-Type": "application/json",
      },
    }
  );
  return jaffarAnswer.data.answer;
}

function scroll() {
  let container = document.querySelector("#messages");
  console.log(container.scrollHeight);
  container.scrollTop = container.scrollHeight + 2000;
}

//////////////////////////////////////////////////
// Form
/////////////////////////////////////////////////
async function getConfig() {
  try {
    // Essayer d'abord l'appel API
    const questions = await axios.get('/pc-analytics-jaffar/jaffar/configs/get?file=jaffarConfig');
    return questions.data.questions;
  } catch (error) {
    console.warn("Échec de l'appel API pour les questions, utilisation du fichier local comme solution de secours");
    // En cas d'échec, utiliser le fichier local
    return loadQuestionsFromFallback();
  }
}

async function getCurrentConfigNames(file) {
  currentConfig = await axios.get('/pc-analytics-jaffar/jaffar/configs/get-current-name?file='+file)
  return currentConfig.data
}

function filterObject(obj) {
  return Object.fromEntries(
    Object.entries(obj).filter(
      ([_, value]) =>
        value !== null &&
        value !== undefined &&
        Array.isArray(value) &&
        value.length === 0
    )
  );
}

// Fonction pour charger les questions depuis le fichier JSON local
function loadQuestionsFromFallback() {
  try {
    const questionsElement = document.getElementById('questions-fallback');
    if (questionsElement) {
      const questionsData = JSON.parse(questionsElement.textContent);
      return questionsData.questions || [];
    }
    return [];
  } catch (error) {
    console.error("Erreur lors du chargement des questions depuis le fichier local:", error);
    return [];
  }
}




