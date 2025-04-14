/******************      INTRO       *****************************************
This page manage all the sultan project.
It is not best practice but at the moment the focus is on portability.
@oswald.bernard@hsbc.com
archi link:
*/


/***********************   CONFIG    *************************************/

let escalationQuestionsConfigLocalDB = new PouchDB("eqcDB");


/***********************   ALPINE    *************************************/

function jaffarEscalationStudio() {
  return {
    page:'jaffar-escalation-questions-studio',
    //     Jaffar config page
     escalationQuestionsConfig:[],
     async init(){
     let escalationQuestionsConfig =  await getLocalConfigEscalationQuestion()
     this.escalationQuestionsConfig= escalationQuestionsConfig.questions
     this.$watch("escalationQuestionsConfig", value=>updateLocalDBEscalationQuestion(value))  
    
    
    },
     escalationQuestionConfigsSelectedQuestion:0,
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
     },
       // Jaffar config export
       jaffarConfigExport:'',
       prepTheDataForExport(){
        let exportJaffar={}
  
        exportJaffar._id="jaffarEscalationQuestionsConfig"
  
        exportJaffar.questions=this.escalationQuestionsConfig
        console.log(exportJaffar)
  
        this.jaffarConfigExport = JSON.stringify(exportJaffar)
        return this.page='export-to-jaffar'
       }
  }
}


/***********************   HELPER    *************************************/

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