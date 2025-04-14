/******************      INTRO       *****************************************
This page manage all the sultan project.
It is not best practice but at the moment the focus is on portability.
@oswald.bernard@hsbc.com
archi link:
*/


/***********************   CONFIG    *************************************/

let jaffarConfigLocalDB = new PouchDB("jcDB");
let escalationQuestionsConfigLocalDB = new PouchDB("eqcDB");


/***********************   ALPINE    *************************************/

function sultan() {
  return {
     page: localStorage.getItem('sultan_auth') === 'true' ? 'menu-sultan' : 'password',
     //     Jaffar config page
     jaffarConfigs:[],
     escalationQuestionsConfig:[],
     async init(){
     let jaffarConfigs =  await getLocalConfigJaffar()
     this.jaffarConfigs=jaffarConfigs.questions
     this.$watch("jaffarConfigs", value=>updateLocalDBJaffar(value))
     let escalationQuestionsConfig =  await getLocalConfigEscalationQuestion()
     this.escalationQuestionsConfig= escalationQuestionsConfig.questions
     
     this.$watch("escalationQuestionsConfig", value=>updateLocalDBEscalationQuestion(value))  
    
    
    },

     escalationQuestionConfigsSelectedQuestion:0,
     jaffarConfigsSelectedQuestion:0,
     MoveDownJaffarQuestions(index){
      const currentValueAtTheIndex=this.jaffarConfigs[index] //A
      const futurIndexCurrentValue=this.jaffarConfigs[index-1] //B
      this.jaffarConfigs[index-1]=currentValueAtTheIndex
      this.jaffarConfigs[index]=futurIndexCurrentValue
     },
     MoveUpJaffarQuestions(index){
      const currentValueAtTheIndex=this.jaffarConfigs[index] //A
      const futurIndexCurrentValue=this.jaffarConfigs[index+1] //B
      this.jaffarConfigs[index+1]=currentValueAtTheIndex
      this.jaffarConfigs[index]=futurIndexCurrentValue
     },
     addAQuestionJaffar(){
     let question={}
     question.name=""
     question.template=""
     question.key=""
     question.options=[]
     this.jaffarConfigs.push(question)
     },
      removeAQuestionJaffar(index){
     this.jaffarConfigs.splice(index,1)
     },
     // Jaffar config import page
     importConfig:[],
     async loadConfigJaffar(){
       await deleteLocalDBJaffar()
       jaffarConfigLocalDB = new PouchDB("jcDB");
       await saveLocalDBJaffar(JSON.parse(this.importConfig)["questions"])
       jaffarConfigs =  await getLocalConfigJaffar()
       this.jaffarConfigs = jaffarConfigs.questions
       this.page = 'jaffar-questions-studio'
     },
     // Jaffar config export
     jaffarConfigExport:'',
     prepTheDataForExportJaffar(){
      let exportJaffar={}

      exportJaffar._id="jaffarConfig"

      exportJaffar.questions=this.jaffarConfigs
      console.log(exportJaffar)

      this.jaffarConfigExport = JSON.stringify(exportJaffar)
      return this.page='export-to-jaffar'
     },
     //escalation question
     MoveDownEscalationQuestions(index){
      const currentValueAtTheIndex=this.escalationQuestionsConfig[index] //A
      const futurIndexCurrentValue=this.escalationQuestionsConfig[index-1] //B
      this.escalationQuestionsConfig[index-1]=currentValueAtTheIndex
      this.escalationQuestionsConfig[index]=futurIndexCurrentValue
     },
     MoveUpEscalationQuestions(index){
      const currentValueAtTheIndex=this.escalationQuestionsConfig[index] //A
      const futurIndexCurrentValue=this.escalationQuestionsConfig[index+1] //B
      this.escalationQuestionsConfig[index+1]=currentValueAtTheIndex
      this.escalationQuestionsConfig[index]=futurIndexCurrentValue
     },
     addAQuestionEscalationQuestion(){
     let question={}
     question.name=""
     question.template=""
     question.key=""
     question.options=[]
     this.escalationQuestionsConfig.push(question)
     },
      removeAQuestionEscalationQuestion(index){
     this.escalationQuestionsConfig.splice(index,1)
     }
  }
}


/***********************   HELPER    *************************************/

// JAFFAR
async function getLocalConfigJaffar() {
  // get the localConfig for jaffar

    try {   let localConfig = await jaffarConfigLocalDB.get("jaffarConfig")
      return localConfig
      } catch {
      return saveLocalDBJaffar([])
      }
  
}

async function saveLocalDBJaffar(value){
 const doc = {};
 doc["_id"]="jaffarConfig";
 doc["questions"] = value;
await jaffarConfigLocalDB.put(doc)
return;
}

async function updateLocalDBJaffar(value){
 let doc = await getLocalConfigJaffar() ;
 doc["questions"] = value;
 await jaffarConfigLocalDB.put(doc)
return;
}


async function deleteLocalDBJaffar() {
  return await jaffarConfigLocalDB.destroy()
}

// Escalation question
async function getLocalConfigEscalationQuestion() {

    try {   let localConfig = await escalationQuestionsConfigLocalDB.get("escalationQuestionConfig")
      return localConfig
      } catch {
      return saveLocalDBEscalationQuestion([])
      }
  
}

async function saveLocalDBEscalationQuestion(value){
 const doc = {};
 doc["_id"]="escalationQuestionConfig";
 doc["questions"] = value;
await escalationQuestionsConfigLocalDB.put(doc)
return;
}

async function updateLocalDBEscalationQuestion(value){
 let doc = await getLocalConfigEscalationQuestion() ;
 doc["questions"] = value;
 await escalationQuestionsConfigLocalDB.put(doc)
return;
}


async function deleteLocalDBEscalationQuestion() {
  return await escalationQuestionsConfigLocalDB.destroy()
}