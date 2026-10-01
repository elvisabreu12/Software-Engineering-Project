import React , { useState } from "react";
import "./LoginSignup.css"
import person_icon from "../Assets/person_icon.png";
import password_icon from "../Assets/password_icon.png";
import email_icon from "../Assets/email_icon.png";



const LoginSignup = () => {
  
    const [action,setAction] = useState("Sign Up");
    return(
    <div className="container">
        <div className="header">
            <div className="text">{action}</div>
            <div className="underline"></div>
        </div>
        <div className="inputs">
          {action==="Login"?<div></div>:<div className="input">
                <img src={person_icon}alt="User Icon"></img>
                <input type="text" placeholder="Name"/>
                </div>}
             
                
             <div className="input">
                <img src={email_icon}alt=" email icon"></img>
                <input type="email" placeholder="Email"/>
            
                </div><div className="input">
             
                <img src={password_icon}alt=" password icon"></img>
                <input type="password" placeholder="Password"/>

                </div>
                </div>
                {action==="Sign Up"?<div></div>:<div className="forgot-password">Lost Password? <span>Click Here!</span></div>}
                
                <div className="submit-container">
                    <div className={action==="Login"?"submit gray":"submit"} onClick={()=>{setAction("Sign Up")}}>Sign Up</div>   
                    <div className={action==="Sign Up"?"submit gray":"submit"} onClick={()=>{setAction("Login")}}>Log in</div>      
                    </div>
    </div>
    )
  
};
export default LoginSignup;
